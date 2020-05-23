
"""
Functions for a custom excepthook with automatic debugging and formatting
options.
"""

from __future__ import print_function

import os
import sys
import traceback
import warnings


def get_bool_env_var(var, default=True):
    if var in os.environ:
        val = os.environ[var]
        # Should be guaranteed anyway, since we already checked it's there.
        assert type(val) is str
        orig_val = str(val)
        try:
            val = bool(int(val))
            valid_flag = True
        except ValueError:
            val = default
            valid_flag = False

        if valid_flag and val not in (True, False):
            valid_flag = False

        if not valid_flag:
            warn_str = 'invalid value of flag {}: {}\n(must be 0 or 1)'.format(
                var, orig_val
            )
            warnings.warn(warn_str)
    else:
        assert type(default) is bool, 'default must be of type bool!'
        val = default
    return val


_emph_file_test_fn = None
def set_file_filter(fn):
    """Takes a function that returns True or False for filename absolute paths.

    Influences which parts of custom traceback will get special formatting.
    """
    global _emph_file_test_fn 
    _emph_file_test_fn = fn


def style(s, fg_color_str_or_dict):
    """
    Input can be single `str` which work as input to `colored` calls,
    or dicts with any of {'fg','bg','attr'} pointing to approprite inputs
    to those functions in `colored`. In the case of 'attr', an iterable of valid
    inputs can be passed.

    Requires the `colored` package to actually style anything, but just returns
    the input `s` as-is without this package installed.
    """
    try:
        from colored import fg, bg, attr, stylize
    except ImportError:
        return s

    if type(fg_color_str_or_dict) is str:
        style_strs = [fg(fg_color_str_or_dict)]

    elif type(fg_color_str_or_dict) is dict:
        style_strs = []
        if 'fg' in fg_color_str_or_dict:
            style_strs.append(fg(fg_color_str_or_dict['fg']))

        if 'bg' in fg_color_str_or_dict:
            style_strs.append(bg(fg_color_str_or_dict['bg']))

        if 'attr' in fg_color_str_or_dict:
            vs = fg_color_str_or_dict['attr']
            if type(vs) is str:
                vs = [vs]
            # This will err if vs was neither str nor iterable (intended).
            for v in vs:
                style_strs.append(attr(v))

    elif fg_color_str_or_dict is None:
        return s
    else:
        raise ValueError('expected second arg to be str or dict')

    return stylize(s, *style_strs)


# Options to consider for formatters (preformat_line_fn / etc):
# https://github.com/cknd/stackprinter
# https://pypi.org/project/colored-traceback/
# https://github.com/Qix-/better-exceptions
# - Not sure how this one is able to hook itself in w/o something like
#   modifying PYTHONPATH in ~/.bashrc like I've done to get this to run.
#   Might be interesting.
# https://pygments.org
# - Example use: https://github.com/sentientmachine/\
#   erics_vim_syntax_and_color_highlighting/blob/master/usercustomize.py
# https://github.com/nir0s/backtrace

_last_frame_to_focus_idx = None
_n_frames_to_skip = 0
def format_exception(etype, value, tb, limit=None,
    emphasis_prefix='>', deemphasis_prefix=' ',
    emphasis_prefix_replace=True, deemphasis_prefix_replace=False,
    emphasis_prefix_style=None, emphasis_line_style=None,
    deemphasis_line_style=None, post_emphasis_delim='\n', pre_err_delim='\n',
    stack_summary2lines_fn=None, preformat_lines_fn=None,
    files_to_emphasize=None):
    """
    Args:
    stack_summary2lines_fn (function): If specified, this is called on the
        `StackSummary` to generate lines to process, rather than the summary
        object's own `format()` method.

    See `style` for appropriate input to `*_style` kwargs.
    """
    # etype and value are only used at the end, not in formatting traceback.
    global _last_frame_to_focus_idx
    global _n_frames_to_skip

    if files_to_emphasize is None:
        files_to_emphasize = _emph_file_test_fn
    emph_file_test_fn = files_to_emphasize
    del files_to_emphasize

    if emphasis_prefix_style is None:
        emphasis_prefix_style = {'fg': 'red', 'attr': 'bold'}

    if emphasis_line_style is None:
        emphasis_line_style = {'attr': 'bold'}

    # Note: could pass capture_locals=True to StackSummary.extract based
    # equivalent to this call if I wanted to do something with the locals.

    # A stack summary is *like* a list of FrameSummary objects.
    stack_summary = traceback.extract_tb(tb, limit=limit)

    # Not currently planning to do anything different in the case where the
    # traceback might pass from lines w/ `emph_file_test_fn` True, then False,
    # then back to True.
    emphasis_idx = None
    for i, frame_summary in enumerate(stack_summary):
        if emph_file_test_fn and emph_file_test_fn(frame_summary.filename):
            emphasis_idx = i

    if emphasis_idx is not None:
        _last_frame_to_focus_idx = emphasis_idx
        _n_frames_to_skip = (len(stack_summary) - 1) - emphasis_idx

    stylized_emph_prefix = style(emphasis_prefix, emphasis_prefix_style)
    def modify_line(single_line, emph=True):
        if emph:
            prefix = emphasis_prefix
            replace_flag = emphasis_prefix_replace
            style_input = emphasis_line_style
        else:
            prefix = deemphasis_prefix
            replace_flag = deemphasis_prefix_replace
            style_input = deemphasis_line_style

        if replace_flag:
            # Important this happens before `style`, because that adds sequences
            # of characters that should not be modified.
            single_line = single_line[len(prefix):]

        # So that the appropriate len() is used in conditional above.
        if emph:
            prefix = stylized_emph_prefix

        single_line = style(single_line, style_input)
        return prefix + single_line

    if stack_summary2lines_fn:
        lines = stack_summary2lines_fn(stack_summary)
    else:
        lines = stack_summary.format()

    if preformat_lines_fn:
        lines = preformat_lines_fn(lines)

    past_emphasis = False
    new_lines = ['Traceback (most recent call last):\n']
    for i, line in enumerate(lines):
        # TODO do any available traceback colorizing libraries provide functions
        # to generate single colored lines from frame_summary objects?
        # if so, maybe use them here before making my modifications
        # (if able to import)
        if i == emphasis_idx:
            # Each element can contain multiple lines (seems to be 2 by default,
            # in circumstances I've seen) (internal newline).
            parts = line.split('\n')
            new_line = '\n'.join([
                modify_line(p) if p else '' for p in parts
            ])
            past_emphasis = True

        elif past_emphasis:
            parts = line.split('\n')
            new_line = '\n'.join([
                modify_line(p, emph=False) if p else '' for p in parts
            ])
            # Doing this here so it's not printed if there are no lines to
            # de-emphasize following the lines to emphasize.
            if post_emphasis_delim:
                new_line = post_emphasis_delim + new_line
                post_emphasis_delim = None
        else:
            new_line = line

        new_lines.append(new_line)

    if pre_err_delim is None:
        pre_err_delim = ''

    new_lines.extend([pre_err_delim] +
        traceback.format_exception_only(etype, value)
    )
    return new_lines


def print_exception(etype, value, tb, **kwargs):
    for line in format_exception(etype, value, tb, **kwargs):
        print(line, file=sys.stderr, end='')


def ipdb__init_pdb(context=3, commands=[], **kwargs):
    """Adds `kwargs` passed to debugger constructor"""
    import ipdb
    try:
        p = ipdb.__main__.debugger_cls(context=context, **kwargs)
    except TypeError:
        p = ipdb.__main__.debugger_cls(**kwargs)
    p.rcLines.extend(commands)
    return p


def ipdb_post_mortem(tb=None, **kwargs):
    """Adds `kwargs` passed to debugger constructor"""
    import ipdb
    ipdb.__main__.wrap_sys_excepthook()
    p = ipdb.__main__._init_pdb(**kwargs)
    p.reset()
    if tb is None:
        tb = sys.exc_info()[2]
    if tb:
        p.interaction(None, tb)


def monkey_patch_ipdb():
    import ipdb
    ipdb.__main__._init_pdb = ipdb__init_pdb
    ipdb.__main__.post_mortem = ipdb_post_mortem
    ipdb.post_mortem = ipdb_post_mortem


_pdb_up_n_lines = None
# Copied from cpython pdb source.
def pdb_interaction(self, frame, traceback):
    """
    Same as in cpython `pdb` source, except manipulation of `sys.stdout`
    (and, in the case where `ipdb` is not available, of `.pdbrc`).
    """
    global _pdb_up_n_lines

    from pdb import Pdb
    import signal

    # Restore the previous signal handler at the Pdb prompt.
    # TODO TODO TODO fix the error this line throws (no attribute)
    # (in !ipdb case only)
    # (it it `None` as a variable defined inside `Pdb` class def... why
    # is it not set here???)
    if Pdb._previous_sigint_handler:
        try:
            signal.signal(signal.SIGINT, Pdb._previous_sigint_handler)
        except ValueError:  # ValueError: signal only works in main thread
            pass
        else:
            Pdb._previous_sigint_handler = None

    f = open(os.devnull, 'w')
    last_stdout = sys.stdout
    sys.stdout = f

    try:
        import ipdb
        have_ipdb = True
    except ImportError:
        assert _pdb_up_n_lines is not None
        have_ipdb = False

        pdbrc = os.path.expanduser('~/.pdbrc')
        if not os.path.isfile(pdbrc):
            orig_pdbrc_data = ''
        else:
            with open(pdbrc, 'r') as f:
                orig_pdbrc_data = f.read()

        cmd_lines = ['u'] * _pdb_up_n_lines
        # may not work in windows case
        pdbrc_data = orig_pdbrc_data + '\n'.join(cmd_lines)

        with open(pdbrc, 'w') as f:
            f.write(pdbrc_data)

    # This is the line that ultimately excecute commands in .pdbrc
    if self.setup(frame, traceback):
        # no interaction desired at this time (happens if .pdbrc contains
        # a command like "continue")
        self.forget()
        return

    sys.stdout = last_stdout
    if not have_ipdb:
        if len(orig_pdbrc_data) > 0:
            with open(pdbrc, 'w') as f:
                f.write(orig_pdbrc_data)
        else:
            os.remove(pdbrc)

    self.print_stack_entry(self.stack[self.curindex])
    _pdb_up_n_lines = None
    self._cmdloop()
    self.forget()


def monkey_patch_pdb():
    """
    Change `pdb.interaction` to only show output right before entering command
    loop again.
    """
    import pdb
    pdb.Pdb.interaction = pdb_interaction


def excepthook(etype, value, tb):
    # TODO allow customizing which errors to skip w/ some kind of config file?

    # RHS check is *not* equivalent to `sys.flags.interactive`.
    # It is the appropriate check here.
    if issubclass(etype, SyntaxError) or hasattr(sys, 'ps1'):
        # TODO maybe still format differently here, particularly if the
        # formatting is just coloring.
        sys.__excepthook__(etype, value, tb)
    else:
        custom_print_exception = get_bool_env_var('PYMISTAKE_TRACEBACK',
            default=True
        )
        if custom_print_exception:
            # TODO TODO TODO document ways in which moving the debugger up the
            # correct number of frames depends on this custom printing function
            # (and try to rewrite so there is no such dependence)
            print_exception(etype, value, tb)
        else:
            traceback.print_exception(etype, value, tb)

        start_post_mortem = get_bool_env_var('PYMISTAKE_DEBUG_UNCAUGHT',
            default=True
        )
        if not start_post_mortem:
            return 
        del start_post_mortem

        # TODO is this also necessary for ipdb case? i think it was, but
        # double check, and only run if needed
        monkey_patch_pdb()
        try:
            # This will trigger the same ImportError.
            # Needs to come first, otherwise the `post_mortem` returned by the
            # import will point to the original thing.
            monkey_patch_ipdb()
            #print('HAVE IPDB1')
            from ipdb import post_mortem
            #print('HAVE IPDB2')
            post_mortem(tb, commands=['u'] * _n_frames_to_skip)

        except ImportError:
            #print('NO IPDB')
            # TODO find some other way to support moving pdb to the correct
            # frame! (maybe modify `.pdbrc` right before, and then set it back?)

            # changing the skip kwarg here did not seem to affect anything...
            #pdb_post_mortem(tb, skip=['pandas*'])
            from pdb import post_mortem

            '''
            if _n_frames_to_skip > 0:
                print('You will need to step up {} stack frames'.format(
                    _n_frames_to_skip
                ))
            '''
            # TODO possible to pass commands here? i don't feel like it was...
            post_mortem(tb)

