import numpy as np, pandas as pd, re
from math import ceil


class DataFeeder(object): # contains data feeds
    def __init__(self, *feeds): # feeds or numpy arrays
        self.feeds = feeds
        self.batsize= None
        feedlens = [x.shape[0] for x in self.feeds]
        assert(feedlens.count(feedlens[0]) == len(feedlens)) # all data feeds must have equal number of examples (axis zero)
        self.size = feedlens[0]
        self.random = True # or False or number
        # iter state
        self.iteridxs = np.arange(self.size)
        self.offset = 0
        self.reset()
        self.autoreset = True

    # fluent settings
    def numbats(self, numbats):
        self.batsize = int(ceil(self.size*1./numbats))
        return self

    def random(self, random):
        self.random = random
        return self

    # batching
    def reset(self):
        if self.random is not False:
            np.random.shuffle(self.iteridxs)
        self.offset = 0

    def hasnextbatch(self):
        ret = self.offset <= self.size-2
        if not ret and self.autoreset:
            self.reset()
        return ret

    def nextbatch(self):
        if self.batsize is None:
            self.offset = self.size # ensure stop
            return [x[:] for x in self.feeds]
        start = self.offset
        end = min(self.offset+self.batsize, self.size)
        sampleidxs = self.iteridxs[start:end]
        self.offset = end
        return [x[sampleidxs] for x in self.feeds]

    def split(self, split=2, random=False): # creates two new datafeeders with disjoint splits
        splitidxs = np.arange(0, self.size)
        if random is not False:
            np.random.shuffle(splitidxs)
        start = 0
        middle = int(ceil(1.*self.size / split))
        end = self.size
        dfvalid = DataFeeder(*[self.splitfeed(feed, splitidxs[start:middle]) for feed in self.feeds])
        dftrain = DataFeeder(*[self.splitfeed(feed, splitidxs[middle:end])   for feed in self.feeds])
        return dftrain, dfvalid

    def isplit(self, splitidxs):
        nsplitidxs = np.setdiff1d(np.arange(0, self.size), splitidxs)
        dfvalid = DataFeeder(*[self.splitfeed(feed, splitidxs)  for feed in self.feeds])
        dftrain = DataFeeder(*[self.splitfeed(feed, nsplitidxs) for feed in self.feeds])
        return dftrain, dfvalid

    def splitfeed(self, feed, idxs):
        if isinstance(feed, DynamicDataFeed):
            return feed.get(idxs)
        else:
            return feed[idxs]


class DataFeed(object):
    '''
    Wraps data, custom data feeders can be implemented for dynamic sampling
    '''
    def __init__(self, data): # data: numpy array
        self.data = data
        self.dtype = data.dtype
        self.shape = data.shape
        self.ndim = data.ndim

class DynamicDataFeed(DataFeed): # a dynamic data generator (e.g. for random negative sampling)
    def __getitem__(self, item):
        pass # TODO

    def get(self, idxs): # create a new Dynamic Data Feed
        pass # TODO

if __name__ == "__main__":
    x = np.random.random((10, 10))
    dx = DataFeed(x)
    print x.ndim, x.shape, x.dtype


class SplitIdxIterator(object):
    def __init__(self, datalen, split=10, random=False, folds=1):
        self.folds = folds
        self.splits = self.buildsplits(datalen, random, split, folds)

    def buildsplits(self, datalen, random, split, folds):    # random: whether and how random, split: percentage in split, folds: how many times to produce a split
        dataidxs = np.arange(0, datalen, 1, dtype="int32")
        if random is not False:     # do random splitting but not Monte Carlo
            if isinstance(random, (int, long)):  # set seed
                np.random.seed(random)
            np.random.shuffle(dataidxs)
        # generate a list of vectors of data indexes
        offset = 0
        splitsize = int(ceil(1. * datalen / split))
        currentfold = 0
        splits = []
        while currentfold < folds:
            start = offset
            end = min(offset + splitsize, datalen)
            splitidxs = dataidxs[start:end]
            splits.append(splitidxs)
            if end == datalen:  # restart
                if random is not False:     # reshuffle
                    np.random.shuffle(dataidxs)
                offset = 0
            currentfold += 1
            offset += splitsize
        return splits

    def __iter__(self):
        self.currentfold = 0
        return self

    def next(self):
        return self.__next__()

    def __next__(self):
        if self.currentfold < self.folds:
            ret = self.splits[self.currentfold]       # get the indexes
            self.currentfold += 1
            return ret
        else:
            raise StopIteration