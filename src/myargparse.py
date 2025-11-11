from dataclasses import dataclass, field
from typing import Any, Callable, Literal, Optional
from types import SimpleNamespace
from argparse import Namespace
import sys


REMAINDER = '...'


@dataclass
class Action:
    dest: str
    option_strings: list[str] = field(default_factory=list)
    nargs: str | int | Literal['?', '*', '+', '...'] | None = None
    const: Any = None
    default: Any = None
    type: Callable[[str], Any] | None = None
    choices: list[str] | None = None
    required: bool = False
    help: str | None = None
    metavar: str | None = None
    action_type: Literal['store', 'store_true', 'store_false', 'version', 'flag_or_explicit'] = 'store'
    version: str | None = None


class MutuallyExclusiveGroup:
    def __init__(self, parser: 'ArgumentParser', required: bool = False):
        self.parser = parser
        self.required = required
        self.actions: list[Action] = []
    
    def add_argument(self, *args, **kwargs) -> Action:
        action = self.parser.add_argument(*args, **kwargs)
        self.actions.append(action)
        return action


class ArgumentParser:
    def __init__(
        self,
        prog: str | None = None,
        description: str | None = None,
        add_help: bool = True,
        parents: list['ArgumentParser'] | None = None,
        formatter_class: type | None = None,
    ):
        self.prog = prog or sys.argv[0] if sys.argv else 'prog'
        self.description = description
        self.actions: list[Action] = []
        self.mutually_exclusive_groups: list[MutuallyExclusiveGroup] = []
        self._option_string_actions: dict[str, Action] = {}
        self._registered_actions: dict[str, type] = {}
        
        if parents:
            for parent in parents:
                self.actions.extend(parent.actions)
                self.mutually_exclusive_groups.extend(parent.mutually_exclusive_groups)
                self._option_string_actions.update(parent._option_string_actions)
        
        if add_help:
            self.add_argument('-h', '--help', action='store_true', help='Show this help message and exit')
    
    def register(self, category: str, name: str, action_class: type) -> None:
        if category == 'action':
            self._registered_actions[name] = action_class
    
    def add_argument(
        self,
        *name_or_flags: str,
        action: str | type = 'store',
        dest: str | None = None,
        nargs: str | int | Literal['?', '*', '+', '...'] | None = None,
        const: Any = None,
        default: Any = None,
        type: Callable[[str], Any] | None = None,
        choices: list[str] | None = None,
        required: bool = False,
        help: str | None = None,
        metavar: str | None = None,
        version: str | None = None,
    ) -> Action:
        option_strings = []
        positional_name = None
        
        for name in name_or_flags:
            if name.startswith('-'):
                option_strings.append(name)
            else:
                if positional_name is not None:
                    raise ValueError(f"Multiple positional arguments not supported: {name_or_flags}")
                positional_name = name
        
        if not option_strings and not positional_name:
            raise ValueError("No argument name provided")
        
        if action == 'store_true':
            action_type = 'store_true'
            default = False if default is None else default
            nargs = 0
        elif action == 'store_false':
            action_type = 'store_false'
            default = True if default is None else default
            nargs = 0
        elif action == 'version':
            action_type = 'version'
            nargs = 0
        elif action == 'flag_or_explicit' or (isinstance(action, str) and action in self._registered_actions):
            action_type = 'flag_or_explicit'
            if nargs is None:
                nargs = '?'
        else:
            action_type = 'store'
            if nargs is None:
                nargs = 1 if option_strings else 1
        
        if dest is None:
            if option_strings:
                # Use the longest option string (like argparse)
                longest = max(option_strings, key=len)
                dest = longest.lstrip('-').replace('-', '_')
            else:
                dest = positional_name
        
        act = Action(
            dest=dest,
            option_strings=option_strings,
            nargs=nargs,
            const=const,
            default=default,
            type=type,
            choices=choices,
            required=required,
            help=help,
            metavar=metavar,
            action_type=action_type,
            version=version,
        )
        
        self.actions.append(act)
        
        for opt in option_strings:
            self._option_string_actions[opt] = act
        
        return act
    
    def add_mutually_exclusive_group(self, required: bool = False) -> MutuallyExclusiveGroup:
        group = MutuallyExclusiveGroup(self, required=required)
        self.mutually_exclusive_groups.append(group)
        return group
    
    def parse_args(self, args: list[str] | None = None) -> SimpleNamespace:
        if args is None:
            args = sys.argv[1:]
        
        namespace, remaining = self._parse_known_args(args)
        
        if remaining:
            # Provide a more helpful error message
            import os
            prog_name = os.path.basename(self.prog)
            if len(remaining) == 1:
                msg = f"unrecognized argument: {remaining[0]}"
            else:
                msg = f"unrecognized arguments: {' '.join(remaining)}"
            print(f"{prog_name}: error: {msg}", file=sys.stderr)
            print(f"Use '{prog_name} --help' for more information.", file=sys.stderr)
            sys.exit(2)
        
        return namespace
    
    def parse_known_args(self, args: list[str] | None = None) -> tuple[SimpleNamespace, list[str]]:
        if args is None:
            args = sys.argv[1:]
        
        return self._parse_known_args(args)
    
    def _parse_known_args(self, args: list[str]) -> tuple[SimpleNamespace, list[str]]:
        namespace = SimpleNamespace()
        seen_action_ids: set[int] = set()
        
        # Set defaults for all actions
        for action in self.actions:
            if action.nargs == REMAINDER:
                # REMAINDER arguments default to empty list
                setattr(namespace, action.dest, [])
            else:
                setattr(namespace, action.dest, action.default)
        
        positionals = [a for a in self.actions if not a.option_strings]
        optionals = [a for a in self.actions if a.option_strings]
        
        remaining: list[str] = []
        i = 0
        while i < len(args):
            arg = args[i]
            
            if arg == '--':
                # Everything after -- goes to remaining
                remaining.extend(args[i + 1:])
                break
            
            if arg.startswith('-'):
                if '=' in arg:
                    opt, value = arg.split('=', 1)
                    if opt in self._option_string_actions:
                        action = self._option_string_actions[opt]
                        if action.action_type == 'flag_or_explicit':
                            self._set_value(namespace, action, value)
                            seen_action_ids.add(id(action))
                            i += 1
                            continue
                    # Unknown option with =, add to remaining
                    remaining.append(arg)
                    i += 1
                    continue
                
                if arg in self._option_string_actions:
                    action = self._option_string_actions[arg]
                    i, consumed = self._consume_optional(action, args, i, namespace, seen_action_ids)
                    continue
                
                # Unknown optional argument - add to remaining and continue
                remaining.append(arg)
                i += 1
                continue
            else:
                if positionals:
                    action = positionals[0]
                    i, consumed = self._consume_positional(action, args, i, namespace, seen_action_ids)
                    if action.nargs != REMAINDER:
                        positionals.pop(0)
                    continue
                else:
                    # No more positionals to consume, add rest to remaining
                    remaining.extend(args[i:])
                    break
            
            i += 1
        
        # Add any remaining args that weren't processed
        if i < len(args):
            remaining.extend(args[i:])
        
        for action in self.actions:
            if action.required and id(action) not in seen_action_ids:
                self.error(f"the following arguments are required: {action.dest}")
        
        for group in self.mutually_exclusive_groups:
            seen = [a for a in group.actions if id(a) in seen_action_ids]
            if group.required and not seen:
                names = [a.option_strings[0] if a.option_strings else a.dest for a in group.actions if a.help]
                self.error(f"one of the arguments {' '.join(names)} is required")
            if len(seen) > 1:
                names = [a.option_strings[0] if a.option_strings else a.dest for a in seen]
                self.error(f"not allowed with argument {' '.join(names)}")
        
        if hasattr(namespace, 'help') and namespace.help:
            self.print_help()
            sys.exit(0)
        
        if hasattr(namespace, 'version') and namespace.version:
            for action in self.actions:
                if action.action_type == 'version':
                    print(action.version)
                    sys.exit(0)
        
        return namespace, remaining
    
    def _consume_optional(self, action: Action, args: list[str], start: int, namespace: SimpleNamespace, seen_action_ids: set[int]) -> tuple[int, int]:
        if action.action_type == 'version':
            setattr(namespace, 'version', True)
            seen_action_ids.add(id(action))
            return start + 1, 0
        
        if action.action_type == 'store_true':
            setattr(namespace, action.dest, True)
            seen_action_ids.add(id(action))
            return start + 1, 0
        
        if action.action_type == 'store_false':
            setattr(namespace, action.dest, False)
            seen_action_ids.add(id(action))
            return start + 1, 0
        
        if action.action_type == 'flag_or_explicit':
            # flag_or_explicit only consumes value if provided with = syntax
            # If just --flag, use const value and don't consume next arg
            setattr(namespace, action.dest, action.const)
            seen_action_ids.add(id(action))
            return start + 1, 0
        
        if action.nargs == 0:
            setattr(namespace, action.dest, action.const)
            seen_action_ids.add(id(action))
            return start + 1, 0
        
        if action.nargs == 1 or action.nargs == '?':
            if start + 1 < len(args) and not args[start + 1].startswith('-'):
                value = args[start + 1]
                self._set_value(namespace, action, value)
                seen_action_ids.add(id(action))
                return start + 2, 1
            elif action.nargs == '?':
                setattr(namespace, action.dest, action.const)
                seen_action_ids.add(id(action))
                return start + 1, 0
            else:
                self.error(f"argument {action.option_strings[0]} requires a value")
        
        if action.nargs == '*' or action.nargs == '+':
            values = []
            i = start + 1
            while i < len(args) and not args[i].startswith('-'):
                values.append(args[i])
                i += 1
            
            if action.nargs == '+' and not values:
                self.error(f"argument {action.option_strings[0]} requires at least one value")
            
            if action.type:
                values = [action.type(v) for v in values]
            if action.choices:
                for v in values:
                    if v not in action.choices:
                        self.error(f"invalid choice: {v} (choose from {', '.join(map(str, action.choices))})")
            
            setattr(namespace, action.dest, values)
            seen_action_ids.add(action)
            return i, len(values)
        
        if isinstance(action.nargs, int):
            if start + action.nargs >= len(args):
                self.error(f"argument {action.option_strings[0]} requires {action.nargs} values")
            values = args[start + 1:start + 1 + action.nargs]
            if action.type:
                values = [action.type(v) for v in values]
            if action.choices:
                for v in values:
                    if v not in action.choices:
                        self.error(f"invalid choice: {v} (choose from {', '.join(map(str, action.choices))})")
            setattr(namespace, action.dest, values if len(values) > 1 else values[0])
            seen_action_ids.add(id(action))
            return start + 1 + action.nargs, action.nargs
        
        self.error(f"unsupported nargs: {action.nargs}")
    
    def _consume_positional(self, action: Action, args: list[str], start: int, namespace: SimpleNamespace, seen_action_ids: set[int]) -> tuple[int, int]:
        if action.nargs == REMAINDER:
            remaining = args[start:]
            setattr(namespace, action.dest, remaining)
            seen_action_ids.add(id(action))
            return len(args), len(remaining)
        
        if action.nargs == '?' or action.nargs == 1:
            if start < len(args):
                value = args[start]
                self._set_value(namespace, action, value)
                seen_action_ids.add(id(action))
                return start + 1, 1
            elif action.nargs == '?':
                setattr(namespace, action.dest, action.const if action.const is not None else action.default)
                if action.const is not None:
                    seen_action_ids.add(id(action))
                return start, 0
            else:
                if action.required:
                    self.error(f"the following arguments are required: {action.dest}")
                return start, 0
        
        if action.nargs == '*' or action.nargs == '+':
            values = []
            i = start
            while i < len(args) and not args[i].startswith('-'):
                values.append(args[i])
                i += 1
            
            if action.nargs == '+' and not values:
                if action.required:
                    self.error(f"the following arguments are required: {action.dest}")
                return start, 0
            
            if action.type:
                values = [action.type(v) for v in values]
            if action.choices:
                for v in values:
                    if v not in action.choices:
                        self.error(f"invalid choice: {v} (choose from {', '.join(map(str, action.choices))})")
            
            setattr(namespace, action.dest, values)
            seen_action_ids.add(id(action))
            return i, len(values)
        
        if isinstance(action.nargs, int):
            if start + action.nargs > len(args):
                self.error(f"argument {action.dest} requires {action.nargs} values")
            values = args[start:start + action.nargs]
            if action.type:
                values = [action.type(v) for v in values]
            if action.choices:
                for v in values:
                    if v not in action.choices:
                        self.error(f"invalid choice: {v} (choose from {', '.join(map(str, action.choices))})")
            setattr(namespace, action.dest, values if len(values) > 1 else values[0])
            seen_action_ids.add(id(action))
            return start + action.nargs, action.nargs
        
        self.error(f"unsupported nargs: {action.nargs}")
    
    def _set_value(self, namespace: SimpleNamespace, action: Action, value: str) -> None:
        if action.type:
            value = action.type(value)
        
        if action.choices and value not in action.choices:
            self.error(f"invalid choice: {value} (choose from {', '.join(map(str, action.choices))})")
        
        setattr(namespace, action.dest, value)
    
    def print_help(self) -> None:
        import os
        import textwrap
        
        # Get just the program name, not the full path
        prog_name = os.path.basename(self.prog)
        
        # Build usage line
        usage_parts = []
        
        # Add optional arguments first
        optionals = [a for a in self.actions if a.option_strings and a.action_type != 'version']
        positionals = [a for a in self.actions if not a.option_strings]
        
        # Handle mutually exclusive groups in usage
        group_options = set()
        for group in self.mutually_exclusive_groups:
            group_opts = []
            for action in group.actions:
                if action.option_strings:
                    opt_str = self._format_action_usage(action)
                    group_opts.append(opt_str)
                    group_options.update(action.option_strings)
            if group_opts:
                usage_parts.append('[' + ' | '.join(group_opts) + ']')
        
        # Add other optional arguments
        for action in optionals:
            if action.option_strings[0] not in group_options:
                opt_str = self._format_action_usage(action)
                usage_parts.append(f'[{opt_str}]')
        
        # Add positional arguments
        for action in positionals:
            if action.nargs == REMAINDER:
                usage_parts.append(f'[{action.dest} ...]')
            elif action.nargs == '?':
                usage_parts.append(f'[{action.dest}]')
            else:
                usage_parts.append(action.dest)
        
        usage_line = f"usage: {prog_name}"
        if usage_parts:
            usage_line += ' ' + ' '.join(usage_parts)
        print(usage_line)
        
        if self.description:
            print(f"\n{self.description}")
        
        # Print optionals section
        if optionals:
            print("\noptions:")
            for action in optionals:
                if action.action_type == 'version':
                    continue
                self._print_action_help(action)
        
        # Print positionals section
        if positionals:
            print("\npositional arguments:")
            for action in positionals:
                self._print_action_help(action, is_positional=True)
    
    def _format_action_usage(self, action: Action) -> str:
        """Format an action for the usage line."""
        if action.option_strings:
            # For usage line, use shortest option if multiple exist
            opts = min(action.option_strings, key=len)
            if action.action_type == 'flag_or_explicit':
                metavar = action.metavar or 'VALUE'
                return f"{opts}[={metavar}]"
            elif action.nargs == 0:
                return opts
            elif action.nargs == '?':
                metavar = action.metavar or 'VALUE'
                return f"{opts} [{metavar}]"
            elif action.choices:
                choices_str = '{' + ','.join(map(str, action.choices)) + '}'
                return f"{opts} {choices_str}"
            else:
                metavar = action.metavar or 'VALUE'
                return f"{opts} {metavar}"
        else:
            if action.nargs == REMAINDER:
                return f"{action.dest} ..."
            elif action.nargs == '?':
                return f"[{action.dest}]"
            else:
                return action.dest
    
    def _print_action_help(self, action: Action, is_positional: bool = False) -> None:
        """Print help for a single action."""
        if action.action_type == 'version':
            return
        
        import textwrap
        import shutil
        
        # Format the action name/options
        if action.option_strings:
            opts = ', '.join(action.option_strings)
            if action.action_type == 'flag_or_explicit':
                metavar = action.metavar or 'VALUE'
                name_part = f"  {opts}[={metavar}]"
            elif action.nargs == 0:
                name_part = f"  {opts}"
            elif action.nargs == '?':
                metavar = action.metavar or 'VALUE'
                name_part = f"  {opts} [{metavar}]"
            elif action.choices:
                choices_str = '{' + ','.join(map(str, action.choices)) + '}'
                name_part = f"  {opts} {choices_str}"
            else:
                metavar = action.metavar or 'VALUE'
                name_part = f"  {opts} {metavar}"
        else:
            name = action.dest
            if action.nargs == REMAINDER:
                name = f"{name} ..."
            elif action.nargs == '?':
                name = f"[{name}]"
            name_part = f"  {name}"
        
        # Get terminal width, default to 80
        try:
            width = shutil.get_terminal_size().columns
        except:
            width = 80
        
        # Print name part and help text
        if action.help:
            help_text = action.help
            # Add default if present and not False/None
            if action.default is not None and action.default is not False and action.default != '':
                if isinstance(action.default, str):
                    help_text += f" (default: {action.default})"
                elif not isinstance(action.default, bool):
                    help_text += f" (default: {action.default})"
            
            # argparse uses column 24 for help text alignment
            help_start_col = 24
            name_len = len(name_part)
            
            if name_len < help_start_col:
                # Pad to align help text
                padding = ' ' * (help_start_col - name_len)
                first_line = f"{name_part}{padding}{help_text}"
                # Check if first line fits
                if len(first_line) <= width:
                    print(first_line)
                else:
                    # Need to wrap
                    print(name_part)
                    # Wrap help text starting at column 24
                    help_lines = textwrap.wrap(help_text, width=width - help_start_col, initial_indent=' ' * help_start_col, subsequent_indent=' ' * help_start_col)
                    for line in help_lines:
                        print(line)
            else:
                # Name is too long, put help on next line
                print(name_part)
                help_lines = textwrap.wrap(help_text, width=width - help_start_col, initial_indent=' ' * help_start_col, subsequent_indent=' ' * help_start_col)
                for line in help_lines:
                    print(line)
        else:
            print(name_part)
    
    def error(self, message: str) -> None:
        import os
        prog_name = os.path.basename(self.prog)
        print(f"{prog_name}: error: {message}", file=sys.stderr)
        sys.exit(2)


class HelpFormatter:
    pass

