"""zsh + oh-my-zsh + 插件 + 主题配置。"""

from __future__ import annotations

import os
import shutil

from .base import Task
from .. import utils


class ZshTask(Task):
    id = "zsh"
    name = "配置 zsh + oh-my-zsh"
    description = "安装 zsh、oh-my-zsh，配置插件与主题"
    depends_on = ["apt_mirror"]

    def check(self, cfg, log=None):
        home = utils.real_home()
        if not utils.command_exists("zsh"):
            return False, "zsh 未安装"
        if not os.path.isdir(f"{home}/.oh-my-zsh"):
            return False, "oh-my-zsh 未安装"
        # 校验插件与主题是否已符合配置
        if not self._zshrc_matches(cfg, home):
            return False, "插件/主题待配置"
        return True, "zsh 已配置"

    def run(self, cfg, log=None):
        home = utils.real_home()
        user = utils.real_user()

        if not utils.command_exists("zsh"):
            utils.apt_install(["zsh"], log=log)

        # 安装 oh-my-zsh（无交互）
        if not os.path.isdir(f"{home}/.oh-my-zsh"):
            install_script = getattr(cfg, "OH_MY_ZSH_INSTALL_URL",
                                     "https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh")
            utils.run_cmd(["sh", "-c", f'curl -fsSL "{install_script}" | sh -s -- --unattended'],
                          env={"HOME": home, "USER": user, **os.environ}, log=log)

        # 外部插件 clone
        self._install_external_plugins(cfg, home, log)

        # 主题（powerlevel10k 需 clone）
        theme = getattr(cfg, "ZSH_THEME", "default")
        if theme == "powerlevel10k":
            self._install_p10k(cfg, home, log)

        # 写 .zshrc：插件行 + 主题行 + （p10k 时）跳过向导
        self._write_zshrc(cfg, home, theme, log)

        # 改默认 shell（用真实路径，避免 shell 字面量不展开）
        zsh_path = shutil.which("zsh")
        if zsh_path and self._current_shell(user) != zsh_path:
            utils.run_cmd(["chsh", "-s", zsh_path, user], log=log)

    def _install_external_plugins(self, cfg, home, log) -> None:
        custom = f"{home}/.oh-my-zsh/custom/plugins"
        os.makedirs(custom, exist_ok=True)
        externals = getattr(cfg, "ZSH_EXTERNAL_PLUGINS", {})
        for name, repo in externals.items():
            dest = f"{custom}/{name}"
            if not os.path.isdir(dest):
                utils.run_cmd(["git", "clone", "--depth", "1", repo, dest], log=log)

    def _install_p10k(self, cfg, home, log) -> None:
        custom_themes = f"{home}/.oh-my-zsh/custom/themes"
        os.makedirs(custom_themes, exist_ok=True)
        dest = f"{custom_themes}/powerlevel10k"
        if not os.path.isdir(dest):
            repo = getattr(cfg, "POWERLEVEL10K_REPO",
                           "https://github.com/romkatv/powerlevel10k")
            utils.run_cmd(["git", "clone", "--depth", "1", repo, dest], log=log)

    def _write_zshrc(self, cfg, home, theme, log) -> None:
        zshrc = f"{home}/.zshrc"
        plugins = getattr(cfg, "ZSH_PLUGINS", ["git"])

        # 插件行
        plugins_line = "plugins=(" + " ".join(plugins) + ")"
        utils.replace_or_append(zshrc, r"^plugins=", plugins_line, plugins_line)

        # 主题行
        if theme == "default":
            theme_val = "robbyrussell"
        elif theme == "random":
            theme_val = "random"
        else:  # powerlevel10k
            theme_val = "powerlevel10k/powerlevel10k"
        theme_line = f'ZSH_THEME="{theme_val}"'
        utils.replace_or_append(zshrc, r"^ZSH_THEME=", theme_line, theme_line)

        # p10k 跳过首次交互向导
        if theme == "powerlevel10k":
            wizard_line = "POWERLEVEL9K_DISABLE_CONFIGURATION_WIZARD=true"
            utils.replace_or_append(zshrc, r"^POWERLEVEL9K_DISABLE_CONFIGURATION_WIZARD=",
                                    wizard_line, wizard_line)

    def _zshrc_matches(self, cfg, home) -> bool:
        """校验 .zshrc 中插件与主题行是否符合配置。"""
        lines = utils.read_lines(f"{home}/.zshrc")
        text = "\n".join(lines)
        plugins = getattr(cfg, "ZSH_PLUGINS", ["git"])
        expected_plugins = "plugins=(" + " ".join(plugins) + ")"
        if expected_plugins not in text:
            return False
        theme = getattr(cfg, "ZSH_THEME", "default")
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
    def _current_shell(user: str) -> str:
        try:
            import pwd

            return pwd.getpwnam(user).pw_shell
        except (ImportError, KeyError):
            return ""
