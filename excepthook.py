
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


def excepthook(etype, value, tb):
    # RHS check is *not* equivalent to `sys.flags.interactive`.
    # It is the appropriate check here.
    if issubclass(etype, SyntaxError) or hasattr(sys, 'ps1'):
        # TODO maybe still format differently here, particularly if the
        # formatting is just coloring.
        sys.__excepthook__(etype, value, tb)
    else:
        print_exception(etype, value, tb)

        # maybe start `ipdb` as he mentions you could start `code`?
        # (can `code.interact` do anything not in `ipdb.post_mortem()`?)
        # https://stackoverflow.com/questions/242485
        get_last_tb = \
            lambda tb=tb: get_last_tb(tb.tb_next) if tb.tb_next else tb
        last_tb = get_last_tb()
        last_frame = last_tb.tb_frame
        import ipdb; ipdb.set_trace()

        # TODO TODO maybe having the locals are what it would take to
        # successfully init a debugging an an arbitrary frame (as i want to
        # below)? (and it doesn't seem tb passed to excepthook provides them)

        # TODO maybe make all lines but the line of interest a little darker
        # than usual terminal white color? or add space after [+ before?] line?
        # or is there a good color to make the line more noticeable
        # (white is pretty easy to read though...)?
        # caret pointing to offending line?

        # TODO TODO if possible, initialize debugger to deepest frame that was
        # in some of my code (so probably test [installed w/ pip + editable] OR
        # not installed?)
        # (seems like it would be possible w/ SO post `code` approach, but
        # [i]pdb (and in a way that deeper frames beyond my code could still be
        # reached?)

        # TODO from !help(ipdb.set_trace), it has a frame kwarg.
        # would passing a frame from tb produce similar effect to postmortem?
        # just set_trace w/ the old frame then? anything specific to post
        # mortem that i actually want?
        # TODO some unique ID for current execution point / context (frame?)
        # that same in set_trace(frame=frame) and post_mortem(tb)? check?
        #import ipdb
        # TODO maybe try w/ "first" frame? change language to highest / deepest
        # probably (or oldest / newest)
        #ipdb.set_trace(frame=last_frame)

        # TODO TODO maybe copy some of ipdb.post_mortem / ipdb.set_trace source?
        # (if ipdb available, cause would prob need their dependencies)

        # TODO uncomment this code if can't get set_trace() above to do more of
        # what i want
        '''
        try:
            from ipdb import post_mortem
        except ImportError:
            from pdb import post_mortem

        # TODO it looks like this also screws with sys.excepthook
        # (from looking at code). maybe set it back to mine after call?
        # the current behavior may be what i want.
        post_mortem(tb)
        '''

