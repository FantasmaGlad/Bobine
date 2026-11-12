"""Complétion des interpréteurs de commandes, calculée depuis un analyseur d'arguments."""

from __future__ import annotations

import argparse
from typing import Any


def _command_tree(parser: argparse.ArgumentParser) -> tuple[list[str], dict[str, dict[str, Any]]]:
    def options(p: argparse.ArgumentParser) -> list[str]:
        return sorted({o for a in p._actions for o in a.option_strings if o.startswith("-") and o not in ("-h", "--help")})

    def subparsers(p: argparse.ArgumentParser) -> dict[str, argparse.ArgumentParser]:
        for action in p._actions:
            if isinstance(action, argparse._SubParsersAction):
                return dict(action.choices)
        return {}

    tree: dict[str, dict[str, Any]] = {}
    for name, command in subparsers(parser).items():
        tree[name] = {"options": options(command), "subs": {sub: options(p) for sub, p in subparsers(command).items()}}
    return options(parser), tree


def completion_script(shell: str, parser: argparse.ArgumentParser) -> str:
    glob, tree = _command_tree(parser)
    commands = " ".join(tree)
    if shell == "fish":
        lines = ["# Complétion de bobine pour fish : bobine completion fish > ~/.config/fish/completions/bobine.fish",
                 "complete -c bobine -f", f"complete -c bobine -n '__fish_use_subcommand' -a '{commands}'"]
        lines += [f"complete -c bobine -l {o.lstrip('-')}" if o.startswith("--") else f"complete -c bobine -s {o.lstrip('-')}" for o in glob]
        for name, info in tree.items():
            if info["subs"]:
                lines.append(f"complete -c bobine -n '__fish_seen_subcommand_from {name}' -a '{' '.join(info['subs'])}'")
            for o in info["options"]:
                flag = f"-l {o[2:]}" if o.startswith("--") else f"-s {o[1:]}"
                lines.append(f"complete -c bobine -n '__fish_seen_subcommand_from {name}' {flag}")
        return "\n".join(lines) + "\n"
    cases = []
    for name, info in tree.items():
        subs = " ".join(info["subs"])
        opts = " ".join(sorted(set(info["options"]) | {o for v in info["subs"].values() for o in v}))
        cases.append(f"    {name})\n        if [ \"$cword\" -le $(( cmd_index + 1 )) ] && [[ \"$cur\" != -* ]]; then\n"
                     f"            COMPREPLY=($(compgen -W \"{subs}\" -- \"$cur\")); return\n        fi\n"
                     f"        COMPREPLY=($(compgen -W \"{opts} $global\" -- \"$cur\")) ;;")
    header = "# Complétion de bobine : source <(bobine completion bash)   (zsh : autoload -U +X bashcompinit && bashcompinit d'abord)\n"
    return header + (
        "_bobine() {\n"
        "    local cur=\"${COMP_WORDS[COMP_CWORD]}\" cword=$COMP_CWORD cmd cmd_index=0 i\n"
        f"    local global=\"{' '.join(glob)}\" commands=\"{commands}\"\n"
        "    for i in \"${!COMP_WORDS[@]}\"; do\n"
        "        [ \"$i\" -eq 0 ] && continue\n"
        "        case \" $commands \" in *\" ${COMP_WORDS[$i]} \"*) cmd=${COMP_WORDS[$i]}; cmd_index=$i; break ;; esac\n"
        "    done\n"
        "    if [ -z \"$cmd\" ]; then\n"
        "        COMPREPLY=($(compgen -W \"$commands $global\" -- \"$cur\")); return\n"
        "    fi\n"
        "    case \"$cmd\" in\n" + "\n".join(cases) + "\n    esac\n}\n"
        "complete -F _bobine bobine\n"
    )
