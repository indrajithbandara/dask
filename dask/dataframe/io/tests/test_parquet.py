import os
import numpy as np
import pandas as pd
import pytest

import dask
from dask.utils import tmpdir
import dask.dataframe as dd
from dask.dataframe.io.parquet import read_parquet, to_parquet
from dask.dataframe.utils import assert_eq
fastparquet = pytest.importorskip('fastparquet')


def test_local():
    with tmpdir() as tmp:
        tmp = str(tmp)
        data = pd.DataFrame({'i32': np.arange(1000, dtype=np.int32),
                             'i64': np.arange(1000, dtype=np.int64),
                             'f': np.arange(1000, dtype=np.float64),
                             'bhello': np.random.choice(['hello', 'you', 'people'], size=1000).astype("O")})
        df = dd.from_pandas(data, chunksize=500)

        to_parquet(tmp, df, write_index=False)

        files = os.listdir(tmp)
        assert '_metadata' in files
        assert 'part.0.parquet' in files

        df2 = read_parquet(tmp, index=False)

        assert len(df2.divisions) > 1

        out = df2.compute(get=dask.get).reset_index()

        for column in df.columns:
            assert (data[column] == out[column]).all()


df = pd.DataFrame({'x': [6, 2, 3, 4, 5],
                   'y': [1.0, 2.0, 1.0, 2.0, 1.0]},
                  index=pd.Index([10, 20, 30, 40, 50], name='myindex'))


@pytest.fixture
def fn(tmpdir):
    ddf = dd.from_pandas(df, npartitions=3)
    to_parquet(str(tmpdir), ddf)

    return str(tmpdir)


def test_index(fn):
    ddf = read_parquet(fn)
    assert_eq(df, ddf)


def test_auto_add_index(fn):
    ddf = read_parquet(fn, columns=['x'], index='myindex')
    assert_eq(df[['x']], ddf)


def test_index_column(fn):
    ddf = read_parquet(fn, columns=['myindex'], index='myindex')
    assert_eq(df[[]], ddf)


def test_index_column_no_index(fn):
    ddf = read_parquet(fn, columns=['myindex'])
    assert_eq(df[[]], ddf)


def test_index_column_false_index(fn):
    ddf = read_parquet(fn, columns=['myindex'], index=False)
    assert_eq(pd.DataFrame(df.index), ddf, check_index=False)


def test_no_columns_yes_index(fn):
    ddf = read_parquet(fn, columns=[], index='myindex')
    assert_eq(df[[]], ddf)


def test_no_columns_no_index(fn):
    ddf = read_parquet(fn, columns=[])
    assert_eq(df[[]], ddf)


def test_series(fn):
    ddf = read_parquet(fn, columns=['x'])
    assert_eq(df[['x']], ddf)

    ddf = read_parquet(fn, columns='x', index='myindex')
    assert_eq(df.x, ddf)


def test_names(fn):
    assert set(read_parquet(fn).dask) == set(read_parquet(fn).dask)
    assert (set(read_parquet(fn).dask) !=
            set(read_parquet(fn, columns=['x']).dask))
    assert (set(read_parquet(fn, columns='x').dask) !=
            set(read_parquet(fn, columns=['x']).dask))
    assert (set(read_parquet(fn, columns=('x',)).dask) ==
            set(read_parquet(fn, columns=['x']).dask))


@pytest.mark.parametrize('c', [['x'], 'x', ['x', 'y'], []])
def test_optimize(fn, c):
    ddf = read_parquet(fn)
    assert_eq(df[c], ddf[c])
    x = ddf[c]

    dsk = x._optimize(x.dask, x._keys())
    assert len(dsk) == x.npartitions
    assert all(v[4] == c for v in dsk.values())
