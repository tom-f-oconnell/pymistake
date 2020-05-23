#!/usr/bin/env python

import site

def main():
    if site.ENABLE_USER_SITE:
        print('This Python should work! Follow installation instructions.')
    else:
        print('This Python will NOT work, because site.ENABLE_USER_SITE is '
            'False. If using a virtual environment, you can try making a new '
            'environment with the --system-site-packages flag, and rechecking '
            'with this script.'
        )


if __name__ == '__main__':
    main()

