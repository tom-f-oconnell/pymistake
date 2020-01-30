
"""
Functions for a custom excepthook with automatic debugging and formatting
options.
"""

from __future__ import print_function

import sys
import traceback


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

# traceback.print_tb seems equivalent to print(''.join(traceback.format_tb(tb)))
# (in cpython source code, this is what it actually is:
# traceback.print_list(traceback.extract_tb(tb, limit=limit), file=file)
# then print_list prints each element in:
# StackSummary.from_list(extracted_list).format()

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


def pdb_post_mortem(t=None, **kwargs):
    """Same as in cpython source, apart from addition of `kwargs`."""
    import pdb
    # handling the default
    if t is None:
        # sys.exc_info() returns (type, value, traceback) if an exception is
        # being handled, otherwise it returns None
        t = sys.exc_info()[2]
    if t is None:
        raise ValueError("A valid traceback must be passed if no "
                         "exception is being handled")
    p = pdb.Pdb(**kwargs)
    p.reset()
    p.interaction(None, t)


''''
def tb_head(tb, n):
    # TODO TODO fallback if python version doesn't support this
    # (prob before calling this fn / raise err / ret None)
    from types import TracebackType
    assert type(n) is int and n > 0

    tb_list = []
    curr_tb = tb
    #for i in range(n - 1):
    for i in range(n):
        tb_list.append(curr_tb)
        curr_tb = tb.tb_next
    # Tried this, but attribute is not writable
    #curr_tb.tb_next = None

    for i, t in enumerate(tb_list[::-1]):
        new_tb = TracebackType(
            None if i == 0 else new_tb, t.tb_frame, t.tb_lasti, t.tb_lineno
        )
    return new_tb


def ith_frame(tb, i):
    for j, (frame, lineno) in enumerate(traceback.walk_tb(tb)):
        if j == i:
            return frame
    raise IndexError('ran out of frames before i={}'.format(i))
'''


def excepthook(etype, value, tb):
    # RHS check is *not* equivalent to `sys.flags.interactive`.
    # It is the appropriate check here.
    if issubclass(etype, SyntaxError) or hasattr(sys, 'ps1'):
        # TODO maybe still format differently here, particularly if the
        # formatting is just coloring.
        sys.__excepthook__(etype, value, tb)
    else:
        print_exception(etype, value, tb)

        # TODO if possible, initialize debugger to deepest frame that was
        # in some of my code
        # https://stackoverflow.com/questions/242485
        # (seems like it would be possible w/ SO post `code` approach, but
        # [i]pdb (and in a way that deeper frames beyond my code could still be
        # reached?)
        # starting to feel like it may not be possible...

        # Would only work in Python3.7. Not possible to modify traceback
        # from Python code before that.
        #tbh = tb_head(tb, _last_frame_to_focus_idx + 1)
        #print_exception(etype, value, tbh)

        # didn't work.
        #frame = ith_frame(tb, _last_frame_to_focus_idx)
        #import ipdb; ipdb.set_trace(frame=frame)
        # neighter did walking back from tb.tb_frame w/ frame.f_back

        try:
            # This will trigger the same ImportError.
            # Needs to come first, otherwise the `post_mortem` returned by the
            # import will point to the original thing.
            monkey_patch_ipdb()
            from ipdb import post_mortem
            post_mortem(tb, commands=['u'] * _n_frames_to_skip)

        except ImportError:
            # changing the skip kwarg here did not seem to affect anything...
            #pdb_post_mortem(tb, skip=['pandas*'])
            from pdb import post_mortem

            if _n_frames_to_skip > 0:
                print('You will need to step up {} stack frames'.format(
                    _n_frames_to_skip
                ))

            # TODO possible to pass commands here? i don't feel like it was...
            post_mortem(tb)

