
"""
Functions for a custom excepthook with automatic debugging and formatting
options.
"""

from __future__ import print_function

import os
import sys
import traceback
import warnings

from util import get_bool_env_var, _debug


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

_n_frames_to_skip = None
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
    if emph_file_test_fn:
        for i, frame_summary in enumerate(stack_summary):
            if _debug:
                print('frame_summary index:', i)
                print('calling test fn: ', emph_file_test_fn.__name__)
                print()

            should_emph = emph_file_test_fn(frame_summary.filename)
            if _debug:
                print('{}({}) = {}'.format(emph_file_test_fn.__name__,
                    frame_summary.filename, should_emph
                ))
                print()

            # As long as the comment above this loop stays true, no need to
            # check anything else here.
            if should_emph:
                emphasis_idx = i

    _n_frames_to_skip = 0
    if emphasis_idx is not None:
        # TODO was there some reason i couldn't count this with a separate fn?
        # try to factor out, so printing can be left to default without losing 
        # the ability to compute this!!!
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


# TODO maybe expose this as an environment variable, for configuration
STDOUT_TO_NULL_IN_INTERACT = True

# TODO summarize how this function works
# Copied from cpython pdb source.
def pdb_interaction(self, frame, traceback):
    """
    Same as in cpython `pdb` source, except manipulation of `sys.stdout`
    (and, in the case where `ipdb` is not available, of `.pdbrc`).
    """
    global _n_frames_to_skip

    from pdb import Pdb
    import signal

    # Restore the previous signal handler at the Pdb prompt.
    # TODO TODO fix the error this line throws (no attribute)
    # (in !ipdb case only) (still relevant?)
    # (it it `None` as a variable defined inside `Pdb` class def... why
    # is it not set here???)
    if Pdb._previous_sigint_handler:
        try:
            signal.signal(signal.SIGINT, Pdb._previous_sigint_handler)
        except ValueError:  # ValueError: signal only works in main thread
            pass
        else:
            Pdb._previous_sigint_handler = None

    if STDOUT_TO_NULL_IN_INTERACT:
        f = open(os.devnull, 'w')
        self.stdout = f

    try:
        import ipdb
        have_ipdb = True
    except (ModuleNotFoundError, ImportError) as e:
        have_ipdb = False
        assert _n_frames_to_skip is not None, 'call format_exception first'
        cmd_lines = ['u'] * _n_frames_to_skip
        self.rcLines.extend(cmd_lines)

    # This is the line that ultimately excecute commands in ~/.pdbrc
    # (or lines that we manually add to self.rcLines, in this case)
    if self.setup(frame, traceback):
        # no interaction desired at this time (happens if .pdbrc contains
        # a command like "continue")
        # TODO what is the .forget() call really doing though?
        # (summarize here)
        self.forget()
        # TODO when does this return happen?
        return

    # TODO TODO as there is the return above, maybe the appropriate time to
    # re-enable is somewhere else? (need to think about when the early return is
    # triggered, even if it isn't always). when is that branch followed?
    if STDOUT_TO_NULL_IN_INTERACT:
        self.stdout = sys.stdout

    self.print_stack_entry(self.stack[self.curindex])
    # TODO TODO double check that it's not a problem for the `ipdb` case to set
    # this to `None` here. if it is, could maybe just only set this in the `pdb`
    # case?
    _n_frames_to_skip = None
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
            # (rewriting is more important than documenting, if possible)
            print_exception(etype, value, tb)
        else:
            traceback.print_exception(etype, value, tb)

        start_post_mortem = get_bool_env_var('PYMISTAKE_DEBUG_UNCAUGHT',
            default=True
        )
        if not start_post_mortem:
            return 
        del start_post_mortem

        # TODO document what this provides in pdb / ipdb case (same in latter?)
        monkey_patch_pdb()
        try:
            # This will trigger the same ImportError (seems now it's a 
            # ModuleNotFoundError...).
            # Needs to come first, otherwise the `post_mortem` returned by the
            # import will point to the original thing.
            monkey_patch_ipdb()
            from ipdb import post_mortem

            if _debug:
                print('JUST BEFORE CALLING IPDB.POST_MORTEM(tb, ...)')

            assert _n_frames_to_skip is not None, 'call format_exception first'
            post_mortem(tb, commands=['u'] * _n_frames_to_skip)

        # TODO is there some python version where this really was supposed to be
        # an ImportError, rather than a ModuleNotFoundError?? what is the
        # difference between them.
        # This will be triggered by the first line of `monkey_patch_ipdb`, not
        # by the import in this function, that happens immediately after that
        # first call to `monkey_patch_ipdb`.
        except (ModuleNotFoundError, ImportError) as e:
            from pdb import post_mortem
            post_mortem(tb)

