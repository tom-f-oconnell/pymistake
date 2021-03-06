
from __future__ import print_function

import os
from os.path import expanduser, abspath, normpath, dirname, join, split, isdir
import sys
import site
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

_debug = get_bool_env_var('PYMISTAKE_DEBUG', default=False)


def script_is_attended():
    # There may be some circumstances where this does not behave how I want.
    # Could also test __stdout__ in those cases, but it would probably be likely
    # to fail in the same circumstances.
    # https://stackoverflow.com/questions/6108330
    # Docs clarify ambiguity in post above: sys.__std*__ should be more reliable
    # for what I want than sys.std* (b/c redirection after initialization).
    return all([
        sys.__stdin__.isatty(),
        sys.__stdout__.isatty(),
        sys.__stderr__.isatty()
    ])


def is_pymistake_installed(user_site_warning=True):
    if not site.ENABLE_USER_SITE:
        return False

    try:
        user_paths = os.environ['PYTHONPATH'].split(os.pathsep)
    except KeyError:
        user_paths = []

    pymistake_dir = dirname(normpath(abspath(__file__)))
    assert isdir(pymistake_dir)
    in_pythonpath = False
    for p in user_paths:
        if normpath(abspath(p)) == pymistake_dir:
            in_pythonpath = True
            break

    if not site.ENABLE_USER_SITE:
        if user_site_warning:
            # TODO change pymistake to use .pth files to get hook, and test
            # that method does not depend on the --system-site-packages setting
            # (+ change install instructions to just ref. pip installing the
            # package then, as changing PYTHONPATH shouldn't be necessary)
            warnings.warn('pymistake relies on usercustomize.py, which is not '
                'loaded in virtual environments created without the '
                '--system-site-packages. Make new virtual environment with this'
                ' flag.'
            )
        return False

    return in_pythonpath


def envvar_dir_list(env_var, default):
    dirs_str = os.getenv(env_var)
    if dirs_str is None:
        return default
    else:
        # TODO warn if not every element here is either `isabs` or has no
        # slashes in the middle (but use something like split not affecting
        # anymore to test latter)
        dirs = []
        for orig_d in dirs_str.split(':'):
            d = orig_d
            if not d:
                continue

            if '~' not in d and os.path.basename(d) == d:
                dirs.append(d)
            else:
                d = abspath(normpath(expanduser(d)))
                if not isdir(d):
                    warnings.warn(('{} in {} seemed like an absolute path but '
                        'was not a directory').format(orig_d, env_var)
                    )
                dirs.append(d)

        return dirs


editable_dists = None
def file_pip_module_info(abs_path):
    """
    Package name can be found at `module_info.project_name`
    """
    global editable_dists
    # Adapted from Github user nbeaver's pip_file_lookup repo (MIT license)
    # Found through: https://stackoverflow.com/questions/33483818

    # TODO: why is this import so slow?
    try:
        from pip.utils import get_installed_distributions
    except ModuleNotFoundError:
        from pip._internal.utils.misc import get_installed_distributions

    if editable_dists is None:
        # all versions of stuff that could be imported above have this flag?
        editable_dists = get_installed_distributions(editables_only=True)

    for dist in get_installed_distributions():
        # TODO maybe only use a test using this, and remove conditional below?
        '''
        try:
            # Python 3.7+ builtin
            from importlib.resources import contents
        except ImportError:
            try:
                # Backport of above available on PyPi
                from importlib_resources import contents
            except ImportError:
                # TODO warn once that we can't find package resources +
                # say to install importlib_resources w/ pip
                pass
        '''
        # First two tests are insufficient in some cases...
        # RECORDs should be part of .dist-info metadatas
        if dist.has_metadata('RECORD'):
            lines = dist.get_metadata_lines('RECORD')
            paths = [l.split(',')[0] for l in lines]
            paths_absolute = [
                normpath(join(dist.location, p)) for p in paths
            ]
        # Otherwise use pip's log for .egg-info's
        elif dist.has_metadata('installed-files.txt'):
            paths = dist.get_metadata_lines('installed-files.txt')
            paths_absolute = [
                normpath(join(dist.egg_info, p)) for p in paths
            ]

        # This seems to work for at least some editable installed things.
        # (but has problems w/ non-editable stuff)
        elif dist in editable_dists and abs_path.startswith(dist.location):
            rel_path = abs_path[len(dist.location) + 1:]
            if dist.has_resource(rel_path):
                return dist
            else:
                warnings.warn(('expected pip package {} to have resource {}, '
                    'but it did not').format(dist.project_name, rel_path)
                )
        else:
            continue

        if abs_path in paths_absolute:
            return dist

    return None


def is_installed_editable(pip_module_info):
    """Returns whether a pip installed module was installed editable."""
    # https://stackoverflow.com/questions/40530000
    try:
        from pip.utils import dist_is_editable
    except ModuleNotFoundError:
        from pip._internal.utils.misc import dist_is_editable

    return dist_is_editable(pip_module_info)


def dirname_matches_path(dirname, abs_path):
    # Presumably all higher parts of path will be directories.
    if os.path.exists(abs_path) and not isdir(abs_path):
        abs_path, _ = split(abs_path)

    # Base case (on Linux at least, has `abs_path` == '/'
    while len(abs_path) > 1:
        abs_path, basename = split(abs_path)
        if basename == dirname or abs_path == dirname:
            return True
    return False


def under_dir_in_list(dir_list, abs_path):
    """
    `dir_list` can include two things:
        1) Directories that can resolve to absolute paths
        2) Name of any part of the path (exact, must not be splittable into
           multiple directories). If path is not splittable, assumed to belong
           to this category.
    """
    return any([dirname_matches_path(d, abs_path) for d in dir_list])


dev_dirs = None
non_dev_dirs = None
def is_dev_file(f, _debug=_debug):
    """Returns whether it seems file at path `f` is being developed locally.
    """
    global dev_dirs
    global non_dev_dirs
    if _debug:
        print(f, 'IS_DEV_FILE?')

    if dev_dirs is None or non_dev_dirs is None:
        dev_dirs = envvar_dir_list('PYMISTAKE_DEV_DIRS', [expanduser('~')])
        non_dev_dirs = envvar_dir_list('PYMISTAKE_NON_DEV_DIRS',
            ['site-packages', 'dist-packages']
        )
        if _debug:
            print('WHITELIST DIRS:', dev_dirs)
            print('BLACKLIST DIRS:', non_dev_dirs)
            print()

    # So far, this seems to be an effective filter for files that are not
    # locally being developed, as an example, the one error contained these
    # traceback lines:
    # File "/home/.../venv/lib/python3.6/site-packages/pandas/.../base.py", ...
    # File "pandas/_libs/index.pyx", line 108, in pandas._libs.index.Index...
    # where the second line does not refer to a file if treated as a relative
    # path from where the Python script was run.

    # TODO determine whether filtering cython extensions (.pxi,.pyx,probably
    # more), or things like that, would be safer than the current isfile check
    # TODO but this filter could in theory have false positives, if this did
    # happen to be a valid relative path, but the relative path need not refer
    # to the file actually responsible for the error in this case. better test.
    if not os.path.isfile(f):
        if _debug:
            print(f, 'IS REAL FILE?', os.path.isfile(f))
        return False

    f = abspath(f)

    # TODO TODO maybe the precedence between white and blacklist should always
    # go to whichever is more specific for a file / directory?
    if under_dir_in_list(non_dev_dirs, f):
        if _debug:
            print(f, 'WAS ON BLACKLIST')
        return False

    if under_dir_in_list(dev_dirs, f):
        if _debug:
            print(f, 'WAS ON WHITELIST')
        return True

    try:
        import pip
        have_pip = True
    except ImportError:
        have_pip = False

    if _debug:
        print('IN WHITELIST?', under_dir_in_list(dev_dirs, f))
        print('IN BLACKLIST?', under_dir_in_list(non_dev_dirs, f))

    # TODO TODO TODO how important was this again?
    # document what is gained by installing this, and if it's actually
    # important, maybe include it in a requirements.txt (or at least a version
    # of that is clear to be "recommended", not strictly required)?
    if have_pip:
        pip_module_info = file_pip_module_info(f)
        if pip_module_info:
            if _debug:
                print('PIP MODULE:', pip_module_info)
                print('EDITABLE?', is_installed_editable(pip_module_info))
            return is_installed_editable(pip_module_info)

        if _debug:
            print('NOT A PIP MODULE')
    else:
        if _debug:
            print('NO PIP')

    if _debug:
        print('NOT CAUGHT BY ANY ABOVE CONDITION')
    # TODO what to do here? try and find cases that reach here
    return False

