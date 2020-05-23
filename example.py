#!/usr/bin/env python3

import pandas as pd

from util import is_pymistake_installed


def main():
    if not is_pymistake_installed():
        raise RuntimeError('your local pymistake repo must be on PYTHONPATH')

    url = \
        'https://raw.githubusercontent.com/mwaskom/seaborn-data/master/iris.csv'
    df = pd.read_csv(url)
    # 'sepal_len' is NOT among the columns of `df`, so this will cause an error
    df.set_index(['sepal_len'])

    # TODO fix double print of ipdb lines in (actually i think it's desired.
    # it's stepping up so the debugger is started in our code.)
    #import ipdb; ipdb.set_trace()


if __name__ == '__main__':
    main()

