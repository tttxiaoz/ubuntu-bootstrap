"""zsh + oh-my-zsh + 插件 + 主题配置。"""

from __future__ import annotations

import os
import shutil

from ..config.schema import Param
from ..core.task import CheckResult, Context, Task, task
from ..platform import fs, user
from ..platform import sys as psys


@task(
    id="zsh",
    name="配置 zsh + oh-my-zsh",
    description="安装 zsh、oh-my-zsh，配置插件与主题",
    depends_on=("apt_mirror",),
    params=[Param("zsh.theme", "choice", default="default",
                  choices=("default", "random", "powerlevel10k"), label="zsh 主题")],
)
class ZshTask(Task):
    def check(self, ctx: Context) -> CheckResult:
        home = user.real_home()
        if not psys.command_exists("zsh"):
            return CheckResult(False, "zsh 未安装")
        if not os.path.isdir(f"{home}/.oh-my-zsh"):
            return CheckResult(False, "oh-my-zsh 未安装")
        if not self._zshrc_matches(ctx.config, home):
            return CheckResult(False, "插件/主题待配置")
        return CheckResult(True, "zsh 已配置")

    def run(self, ctx: Context) -> None:
        config = ctx.config
        home = user.real_home()
        real = user.real_user()

        if not psys.command_exists("zsh"):
            ctx.apt.install(["zsh"], log=ctx.log.log, tee=ctx.log.stream)

        # 安装 oh-my-zsh（无交互）
        if not os.path.isdir(f"{home}/.oh-my-zsh"):
            install_script = config.get("zsh.oh_my_zsh_url")
            ctx.run_cmd(["sh", "-c", f'curl -fsSL "{install_script}" | sh -s -- --unattended'],
                        env={"HOME": home, "USER": real, **os.environ})

        # 外部插件
        self._install_external_plugins(ctx, home)

        # 主题（powerlevel10k 需 clone）
        theme = config.get("zsh.theme")
        if theme == "powerlevel10k":
            self._install_p10k(ctx, home)

        # 写 .zshrc：插件行 + 主题行 + （p10k 时）跳过向导
        self._write_zshrc(ctx, home)

        # 改默认 shell（用真实路径，避免 shell 字面量不展开）
        zsh_path = shutil.which("zsh")
        if zsh_path and self._current_shell(real) != zsh_path:
            ctx.run_cmd(["chsh", "-s", zsh_path, real])

    def _install_external_plugins(self, ctx: Context, home: str) -> None:
        custom = f"{home}/.oh-my-zsh/custom/plugins"
        os.makedirs(custom, exist_ok=True)
        apt_map = ctx.config.get("zsh.external_plugins_apt") or {}
        for name, pkg in apt_map.items():
            dest = f"{custom}/{name}"
            if os.path.isdir(dest):
                continue
            if not self._install_plugin_apt(ctx, pkg, name, dest):
                ctx.log.log(f"⚠️ 插件 {name} 安装失败（apt 无包或脚本缺失），已跳过",
                            style="yellow")

    def _install_plugin_apt(self, ctx: Context, pkg: str, name: str, dest: str) -> bool:
        """apt 安装插件并 symlink 进 oh-my-zsh custom/plugins；失败返回 False。"""
        try:
            ctx.apt.install([pkg], log=ctx.log.log, tee=ctx.log.stream)
        except psys.TaskError:
            return False
        src = self._find_plugin_script(pkg, name)
        if not src:
            return False
        os.makedirs(dest, exist_ok=True)
        target = f"{dest}/{name}.plugin.zsh"
        if not os.path.exists(target):
            os.symlink(src, target)
        return True

    @staticmethod
    def _find_plugin_script(pkg: str, name: str) -> str | None:
        """定位 apt 安装的插件主脚本（不同发行版路径略有差异）。"""
        candidates = [
            f"/usr/share/{name}/{name}.zsh",
            f"/usr/share/{pkg}/{pkg}.zsh",
            f"/usr/share/{name}/{name}.plugin.zsh",
        ]
        for c in candidates:
            if os.path.isfile(c):
                return c
        return None

    def _install_p10k(self, ctx: Context, home: str) -> None:
        custom_themes = f"{home}/.oh-my-zsh/custom/themes"
        os.makedirs(custom_themes, exist_ok=True)
        dest = f"{custom_themes}/powerlevel10k"
        if not os.path.isdir(dest):
            repo = ctx.config.get("zsh.p10k_repo")
            ctx.run_cmd(["git", "clone", "--depth", "1", repo, dest])

    def _write_zshrc(self, ctx: Context, home: str) -> None:
        zshrc = f"{home}/.zshrc"
        plugins = ctx.config.get("zsh.plugins") or ["git"]
        theme = ctx.config.get("zsh.theme")

        # 插件行
        plugins_line = "plugins=(" + " ".join(plugins) + ")"
        fs.replace_or_append(zshrc, r"^plugins=", plugins_line, plugins_line)

        # 主题行
        if theme == "default":
            theme_val = "robbyrussell"
        elif theme == "random":
            theme_val = "random"
        else:  # powerlevel10k
            theme_val = "powerlevel10k/powerlevel10k"
        theme_line = f'ZSH_THEME="{theme_val}"'
        fs.replace_or_append(zshrc, r"^ZSH_THEME=", theme_line, theme_line)

        # p10k 跳过首次交互向导
        if theme == "powerlevel10k":
            wizard_line = "POWERLEVEL9K_DISABLE_CONFIGURATION_WIZARD=true"
            fs.replace_or_append(zshrc, r"^POWERLEVEL9K_DISABLE_CONFIGURATION_WIZARD=",
                                 wizard_line, wizard_line)

    def _zshrc_matches(self, config, home: str) -> bool:
        """校验 .zshrc 中插件与主题行是否符合配置。"""
        text = "\n".join(fs.read_lines(f"{home}/.zshrc"))
        plugins = config.get("zsh.plugins") or ["git"]
        expected_plugins = "plugins=(" + " ".join(plugins) + ")"
        if expected_plugins not in text:
            return False
        theme = config.get("zsh.theme")
        if theme == "default":
            expected_theme = 'ZSH_THEME="robbyrussell"'
        elif theme == "random":
            expected_theme = 'ZSH_THEME="random"'
        else:
            expected_theme = 'ZSH_THEME="powerlevel10k/powerlevel10k"'
        if expected_theme not in text:
            return False
        return True

    @staticmethod
    def _current_shell(u: str) -> str:
        try:
            import pwd

            return pwd.getpwnam(u).pw_shell
        except (ImportError, KeyError):
            return ""
