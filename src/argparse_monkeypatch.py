import argparse
import sys
import re
from argparse import (
    _StoreAction, OPTIONAL, SUPPRESS, ArgumentError, _re, _get_action_name,
    _UNRECOGNIZED_ARGS_ATTR, REMAINDER, PARSER, ZERO_OR_MORE, ONE_OR_MORE,
    HelpFormatter # Import HelpFormatter base class
)
from gettext import gettext as _, ngettext

# --- 1. Custom Action Class (Unchanged) ---
class FlagOrEqualsValueAction(_StoreAction):
    _only_equals_value = True # Marker attribute
    def __init__(self,
                 option_strings,
                 dest,
                 const=True,
                 default=False,
                 type=None,
                 choices=None,
                 required=False,
                 help=None,
                 metavar=None):
        super().__init__(
            option_strings=option_strings,
            dest=dest,
            nargs='?',
            const=const,
            default=default,
            type=type,
            choices=choices,
            required=required,
            help=help,
            metavar=metavar)

# --- 2. Custom Help Formatter (with two overrides) ---
class CustomHelpFormatter(HelpFormatter):
    """
    Custom help formatter that displays arguments for FlagOrEqualsValueAction
    as '[=METAVAR]' and removes the space in the invocation/usage string.
    """

    # Override 1: Format the argument part itself
    def _format_args(self, action, default_metavar):
        is_special_flag_action = getattr(action, '_only_equals_value', False)
        is_nargs_optional = (action.nargs == OPTIONAL) # OPTIONAL == '?'

        if is_special_flag_action and is_nargs_optional:
            get_metavar = self._metavar_formatter(action, default_metavar)
            metavar_tuple = get_metavar(1)
            metavar_str = metavar_tuple[0] # Get the actual metavar string
            return '[=%s]' % metavar_str
        else:
            return super()._format_args(action, default_metavar)

    # Override 2: Format the full invocation string in the options list
    def _format_action_invocation(self, action):
        is_special_flag_action = getattr(action, '_only_equals_value', False)
        is_nargs_optional = (action.nargs == OPTIONAL)

        if not action.option_strings:
            # Handle positional arguments (delegates to _format_args)
            return super()._format_action_invocation(action)

        elif action.nargs == 0:
             # Handle actions without arguments (e.g., store_true)
             return super()._format_action_invocation(action)

        # Handle actions *with* arguments
        elif is_special_flag_action and is_nargs_optional:
            # Our special action: Combine WITHOUT space
            default_metavar = self._get_default_metavar_for_optional(action)
            args_string = self._format_args(action, default_metavar) # Gets '[=VALUE]'
            return ', '.join(action.option_strings) + args_string # No space here
        else:
            # Other actions with arguments: Combine WITH space (default behavior)
             return super()._format_action_invocation(action)

    # Override 3: Format the parts used to build the usage line
    # We need to modify how the 'part' for our specific action is created
    def _get_actions_usage_parts(self, actions, groups):
        # This is complex, so we modify the specific part generation
        parts = super()._get_actions_usage_parts(actions, groups)

        # Post-process the generated parts specifically for our action
        processed_parts = []
        for part, action in zip(parts, actions): # Need original actions to check
            if part is None: # Skip suppressed actions
                processed_parts.append(None)
                continue

            is_special_flag_action = getattr(action, '_only_equals_value', False)

            if is_special_flag_action and action.option_strings:
                # Original part might look like "[--arg [=VALUE]]"
                # We want "[--arg[=VALUE]]"
                option_string = action.option_strings[0]
                # Rebuild the argument string using our custom _format_args
                default_metavar = self._get_default_metavar_for_optional(action)
                args_string = self._format_args(action, default_metavar) # Gets '[=VALUE]'

                # Combine without space
                combined = option_string + args_string

                # Re-add brackets if it was optional
                if not action.required and action not in self._get_group_actions(groups):
                    processed_parts.append('[%s]' % combined)
                else:
                     processed_parts.append(combined) # Should likely be optional anyway
            else:
                # Keep the original part for other actions
                processed_parts.append(part)

        return [p for p in processed_parts if p is not None] # Filter None again just in case


    # Helper to get all actions belonging to any group in the list
    # (to correctly determine if brackets should be added in _get_actions_usage_parts)
    def _get_group_actions(self, groups):
        group_actions = set()
        for group in groups:
             if hasattr(group, '_group_actions'): # Standard ArgumentGroup/MutuallyExclusiveGroup
                 group_actions.update(group._group_actions)
        return group_actions


# --- 3. Custom ArgumentParser (Unchanged from previous working version) ---
class CustomArgumentParser(argparse.ArgumentParser):
    # ... include the working _parse_known_args override ...
    def _parse_known_args(self, arg_strings, namespace, intermixed=False):
        # This is a near-verbatim copy of ArgumentParser._parse_known_args
        # from Python 3.8-3.11 (adjust imports/logic slightly if using a
        # very different version).
        # Modifications are marked with ### CUSTOM ###

        # === Start of copied _parse_known_args ===
        if self.fromfile_prefix_chars is not None:
            arg_strings = self._read_args_from_files(arg_strings)

        action_conflicts = {}
        for mutex_group in self._mutually_exclusive_groups:
            group_actions = mutex_group._group_actions
            for i, mutex_action in enumerate(mutex_group._group_actions):
                conflicts = action_conflicts.setdefault(mutex_action, [])
                conflicts.extend(group_actions[:i])
                conflicts.extend(group_actions[i + 1:])

        option_string_indices = {}
        arg_string_pattern_parts = []
        arg_strings_iter = iter(arg_strings)
        for i, arg_string in enumerate(arg_strings_iter):
            if arg_string == '--':
                arg_string_pattern_parts.append('-')
                for arg_string in arg_strings_iter:
                    arg_string_pattern_parts.append('A')
            else:
                option_tuples = self._parse_optional(arg_string)
                if option_tuples is None:
                    pattern = 'A'
                else:
                    option_string_indices[i] = option_tuples
                    pattern = 'O'
                arg_string_pattern_parts.append(pattern)

        arg_strings_pattern = ''.join(arg_string_pattern_parts)

        seen_actions = set()
        seen_non_default_actions = set()
        warned = set()

        def take_action(action, argument_strings, option_string=None):
            seen_actions.add(action)
            argument_values = self._get_values(action, argument_strings)

            if action.option_strings or argument_strings:
                seen_non_default_actions.add(action)
                for conflict_action in action_conflicts.get(action, []):
                    if conflict_action in seen_non_default_actions:
                        msg = _('not allowed with argument %s')
                        action_name = _get_action_name(conflict_action)
                        raise ArgumentError(action, msg % action_name)

            if argument_values is not SUPPRESS:
                action(self, namespace, argument_values, option_string)

        # ### CUSTOM ### Modify the consume_optional inner function below ###
        def consume_optional(start_index):
            option_tuples = option_string_indices[start_index]
            if len(option_tuples) > 1:
                options = ', '.join([option_string
                    for action, option_string, sep, explicit_arg in option_tuples])
                args = {'option': arg_strings[start_index], 'matches': options}
                msg = _('ambiguous option: %(option)s could match %(matches)s')
                self.error(msg % args) # Use self.error for consistency

            # Extract the single option tuple.
            action, option_string, sep, explicit_arg = option_tuples[0]

            # Detect if it's our custom action BEFORE deciding how to consume args
            is_special_flag_action = getattr(action, '_only_equals_value', False)

            # Use the original _match_argument for internal checks when needed
            match_argument = self._match_argument
            action_tuples = []

            # Loop for handling combined short options (e.g., -xyz)
            # In our specific case (--arg), this loop will typically run once.
            while True:
                if action is None:
                    extras.append(arg_strings[start_index])
                    extras_pattern.append('O')
                    return start_index + 1

                # ============================================================
                # Core Logic Modification: How many args to consume?
                # ============================================================

                if explicit_arg is not None:
                    # CASE 1: Value provided using '=' (e.g., --arg=apple)
                    # Let the standard argparse logic handle this. It needs to
                    # know the expected number of arguments for the action.
                    arg_count = match_argument(action, 'A') # How many expects? Should be 1 for nargs='?'

                    # --- Standard logic from argparse for explicit_arg ---
                    chars = self.prefix_chars
                    if arg_count == 0 and option_string[1] not in chars and explicit_arg != '':
                         # Handle combined short options like -xval correctly
                         if sep or explicit_arg[0] in chars:
                             msg = _('ignored explicit argument %r')
                             raise ArgumentError(action, msg % explicit_arg)
                         action_tuples.append((action, [], option_string))
                         char = option_string[0]
                         option_string = char + explicit_arg[0]
                         optionals_map = self._option_string_actions
                         if option_string in optionals_map:
                             action = optionals_map[option_string]
                             explicit_arg = explicit_arg[1:]
                             if not explicit_arg: sep = explicit_arg = None
                             elif explicit_arg[0] == '=': sep, explicit_arg = '=', explicit_arg[1:]
                             else: sep = ''
                         else:
                             extras.append(char + explicit_arg)
                             extras_pattern.append('O')
                             stop = start_index + 1; break
                         # Continue loop to process the new action/arg
                         continue

                    elif arg_count == 1:
                        # Expected case for nargs='?': consumes exactly the explicit arg
                        stop = start_index + 1
                        args = [explicit_arg]
                        action_tuples.append((action, args, option_string))
                        break # Exit loop, consumption done

                    else: # arg_count is 0 or > 1
                        # Action expects 0 args (like store_true) or N > 1 args,
                        # but got exactly one via '='. This is an error.
                         msg = _('ignored explicit argument %r')
                         raise ArgumentError(action, msg % explicit_arg)
                    # --- End standard logic for explicit_arg ---

                else:
                    # CASE 2: No '=' used (e.g., --arg or --arg banana)

                    # ### CUSTOM ### Check if it's our special action
                    if is_special_flag_action:
                        # Force consumption of ZERO subsequent arguments.
                        # The value will come from action.const later.
                        arg_count = 0
                        stop = start_index + 1 # Advance parser past the flag itself
                        args = []             # Consumed arguments list is empty
                        action_tuples.append((action, args, option_string))
                        break # Exit loop, consumption done
                    else:
                        # Standard behavior for non-special actions:
                        # See if subsequent tokens match the action's nargs.
                        start = start_index + 1
                        selected_patterns = arg_strings_pattern[start:]
                        arg_count = match_argument(action, selected_patterns)
                        stop = start + arg_count
                        args = arg_strings[start:stop]
                        action_tuples.append((action, args, option_string))
                        break # Exit loop, consumption done
                # ============================================================
                # End of Core Logic Modification
                # ============================================================


            # Process the collected actions
            assert action_tuples
            for action_obj, args_list, opt_str in action_tuples: # Renamed action -> action_obj to avoid shadowing outer scope in loop
                if hasattr(action_obj, 'deprecated') and action_obj.deprecated and opt_str not in warned:
                    self._warning(_("option '%(option)s' is deprecated") %
                                  {'option': opt_str})
                    warned.add(opt_str)
                take_action(action_obj, args_list, opt_str)
            return stop
        # ### END of consume_optional modification ###


        positionals = self._get_positional_actions()

        # (Original consume_positionals logic - unchanged)
        def consume_positionals(start_index):
            match_partial = self._match_arguments_partial
            selected_pattern = arg_strings_pattern[start_index:]
            arg_counts = match_partial(positionals, selected_pattern)
            for action, arg_count in zip(positionals, arg_counts):
                args = arg_strings[start_index: start_index + arg_count]
                # Strip out the first '--' if it is not in REMAINDER arg.
                if action.nargs == PARSER:
                    if start_index < len(arg_strings_pattern) and arg_strings_pattern[start_index] == '-':
                        # Can be '--' or just '-'. Check only if it is '--'.
                        if args and args[0] == '--':
                           args.remove('--')
                elif action.nargs != REMAINDER:
                    if '--' in args:
                       args.remove('--')
                start_index += arg_count
                if args and hasattr(action, 'deprecated') and action.deprecated and action.dest not in warned:
                     self._warning(_("argument '%(argument_name)s' is deprecated") %
                                   {'argument_name': action.dest})
                     warned.add(action.dest)
                take_action(action, args)
            positionals[:] = positionals[len(arg_counts):]
            return start_index


        extras = []
        extras_pattern = []
        start_index = 0
        if option_string_indices:
            max_option_string_index = max(option_string_indices)
        else:
            max_option_string_index = -1

        # (Main parsing loop - unchanged)
        while start_index <= max_option_string_index:
            next_option_string_index = start_index
            while next_option_string_index <= max_option_string_index:
                if next_option_string_index in option_string_indices:
                    break
                next_option_string_index += 1
            if not intermixed and start_index != next_option_string_index:
                positionals_end_index = consume_positionals(start_index)
                if positionals_end_index > start_index:
                    start_index = positionals_end_index
                    continue
                else:
                    start_index = positionals_end_index
            if start_index not in option_string_indices:
                strings = arg_strings[start_index:next_option_string_index]
                extras.extend(strings)
                extras_pattern.extend(arg_strings_pattern[start_index:next_option_string_index])
                start_index = next_option_string_index
            start_index = consume_optional(start_index)

        # (Post-loop processing - unchanged)
        if not intermixed:
             stop_index = consume_positionals(start_index)
             extras.extend(arg_strings[stop_index:])
        else:
             extras.extend(arg_strings[start_index:])
             extras_pattern.extend(arg_strings_pattern[start_index:])
             extras_pattern = ''.join(extras_pattern)
             assert len(extras_pattern) == len(extras)
             # consume all positionals
             arg_strings = [s for s, c in zip(extras, extras_pattern) if c != 'O']
             arg_strings_pattern = extras_pattern.replace('O', '')
             stop_index = consume_positionals(0)
             # leave unknown optionals and non-consumed positionals in extras
             for i, c in enumerate(extras_pattern):
                 if not stop_index:
                     break
                 if c != 'O':
                     stop_index -= 1
                     extras[i] = None
             extras = [s for s in extras if s is not None]


        # (Required checks - unchanged)
        required_actions = []
        for action in self._actions:
            if action not in seen_actions:
                if action.required:
                    required_actions.append(_get_action_name(action))
                else:
                    if (action.default is not None and
                        isinstance(action.default, str) and
                        hasattr(namespace, action.dest) and
                        action.default is getattr(namespace, action.dest)):
                           # Attempt to convert string default now, leaving None as None
                            try:
                                setattr(namespace, action.dest,
                                        self._get_value(action, action.default))
                            except ArgumentError:
                                # Handle cases like FileType where default might not be valid initially
                                pass


        if required_actions:
            self.error(_('the following arguments are required: %s') %
                       ', '.join(required_actions))

        for group in self._mutually_exclusive_groups:
            if group.required:
                for action in group._group_actions:
                    if action in seen_non_default_actions:
                        break
                else:
                    names = [_get_action_name(action)
                             for action in group._group_actions
                             if action.help is not SUPPRESS]
                    msg = _('one of the arguments %s is required')
                    self.error(msg % ' '.join(names))

        # (Return value - unchanged)
        return namespace, extras

if __name__ == '__main__':

    # --- 4. Usage Example (Unchanged) ---
    parser = CustomArgumentParser(
        prog='test_args.py',
        description='Demonstrate flag with mandatory equals for value.',
        formatter_class=CustomHelpFormatter # *** Use the custom formatter ***
    )

    parser.add_argument(
        '--arg',
        action=FlagOrEqualsValueAction,
        const=True,
        default=False,
        metavar='VALUE',
        help="A flag that can optionally take VALUE only via --arg=VALUE"
    )

    parser.add_argument('positional', nargs='?', default=None, help="A positional arg")


    print("Raw sys.argv:", sys.argv)
    try:
        if '-h' in sys.argv or '--help' in sys.argv:
             parser.print_help()
             sys.exit(0)

        args = parser.parse_args()
        print("\nParsed args:")
        print(f"args.arg: {args.arg} (type: {type(args.arg)})")
        print(f"args.positional: {args.positional} (type: {type(args.positional)})")
    except argparse.ArgumentError as e:
        parser.error(str(e))
    except SystemExit:
        pass