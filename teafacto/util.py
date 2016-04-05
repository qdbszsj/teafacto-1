import collections, inspect, argparse, dill as pkl, os, numpy as np, pandas as pd
from datetime import datetime as dt


def loadlexidtsv(path):
    with open(path) as f:
        allgloveids = []    # 2D
        allcharmats = []    # 3D
        allfbids = []       # 1D

        c = 0
        for line in f:
            try:
                ns = line[:-1].split("\t")
                gloveids = map(int, ns[0].split(" "))
                charmat = []
                charsplits = ns[1].split(", ")
                charmat.extend([[int(y) if len(y) > 0 else 0 for y in x.split(" ")] for x in charsplits])
                fbid = int(ns[2])
                allgloveids.append(gloveids)
                allcharmats.append(charmat)
                allfbids.append(fbid)
                if c % 1e6 == 0:
                    print "%.0fM" % (c/1e6)
                c += 1
            except Exception, e:
                print line
                raise e
        allgloveids = makenpmatrix(allgloveids, dtype="int32", toplen=15)
        print "allgloveids made"
        allcharmats = makenptensor(allcharmats, dtype="int32", toplens=(15, 30))
        print "allcharmats made"
        allfbids = np.asarray(allfbids, dtype="int32")
        return allgloveids, allcharmats, allfbids


def makenpmatrix(tomat, dtype="int32", toplen=None):
    if toplen is None:
        maxlen = 0
        for x in tomat:
            maxlen = max(len(x), maxlen)
    else:
        maxlen = toplen
    print maxlen
    i = 0
    while i < len(tomat):
        x = tomat[i]
        if len(x) > maxlen:
            print tomat[i]
            del tomat[i]
            continue
        x.extend([0]*(maxlen - len(x)))
        i += 1
    return np.asarray(tomat, dtype=dtype)


def makenptensor(toten, dtype="int32", toplens=None):
    if toplens is None:
        maxlen1 = 0
        maxlen2 = 0
        for tomat in toten:
            maxlen1 = max(len(tomat), maxlen1)
            for x in tomat:
                maxlen2 = max(len(x), maxlen2)
    else:
        maxlen1 = toplens[0]
        maxlen2 = toplens[1]
    print maxlen1, maxlen2
    for tomat in toten:
        for x in tomat:
            x.extend([0]*(maxlen2 - len(x)))
        torep = [[0]*maxlen2]
        tomat.extend(torep*(maxlen1 - len(tomat)))
    return np.asarray(toten, dtype=dtype)


class ticktock(object):
    def __init__(self, prefix="", verbose=True):
        self.prefix = prefix
        self.verbose = verbose
        self.state = None
        self.perc = None
        self.prevperc = None
        self._tick()
    def tick(self, state=None):
        if self.verbose and state is not None:
            print "%s: %s" % (self.prefix, state)
        self._tick()

    def _tick(self):
        self.ticktime = dt.now()

    def _tock(self):
        return (dt.now() - self.ticktime).total_seconds()

    def progress(self, x, of):
        self.perc = int(round(100.* x/of))
        if self.perc != self.prevperc:
            print "%s: %d" % (self.prefix, self.perc)  + "%"
            self.prevperc = self.perc

    def tock(self, action=None, prefix=None):
        duration = self._tock()
        if self.verbose:
            prefix = prefix if prefix is not None else self.prefix
            action = action if action is not None else self.state
            print "%s: %s in %s" % (prefix, action, self._getdurationstr(duration))
        return self

    def _getdurationstr(self, duration):
        if duration >= 60:
            duration = int(round(duration))
            seconds = duration % 60
            minutes = (duration // 60) % 60
            hours = (duration // 3600) % 24
            days = duration // (3600*24)
            acc = ""
            if seconds > 0:
                acc = ("%d second" % seconds) + ("s" if seconds > 1 else "")
            if minutes > 0:
                acc = ("%d minute" % minutes) + ("s" if minutes > 1 else "") + (", " + acc if len(acc) > 0 else "")
            if hours > 0:
                acc = ("%d hour" % hours) + ("s" if hours > 1 else "") + (", " + acc if len(acc) > 0 else "")
            if days > 0:
                acc = ("%d day" % days) + ("s" if days > 1 else "") + (", " + acc if len(acc) > 0 else "")
            return acc
        else:
            return ("%.3f second" % duration) + ("s" if duration > 1 else "")


def argparsify(f, test=None):
    args, _, _, defaults = inspect.getargspec(f)
    assert(len(args) == len(defaults))
    parser = argparse.ArgumentParser()
    i = 0
    for arg in args:
        parser.add_argument("-%s"%arg, "--%s"%arg, type=type(defaults[i]))
        i += 1
    if test is not None:
        par = parser.parse_args([test])
    else:
        par = parser.parse_args()
    kwargs = {}
    for arg in args:
        if getattr(par, arg) is not None:
            kwargs[arg] = getattr(par, arg)
    return kwargs


def argprun(f):
    f(**argparsify(f))


def issequence(x):
    return isinstance(x, collections.Sequence) and not isinstance(x, basestring)


def isnumber(x):
    return isinstance(x, float) or isinstance(x, int)


def isstring(x):
    return isinstance(x, basestring)


def isfunction(x):
    return hasattr(x, "__call__")


class Saveable(object):
    def __init__(self, autosave=False, **kw):
        super(Saveable, self).__init__(**kw)
        self._autosave = autosave

    ############# Saving and Loading #################"
    def getdefaultsavepath(self):
        dir = "../../saves/"
        if not os.path.exists(os.path.join(os.path.dirname(__file__), dir)):
            os.makedirs(os.path.join(os.path.dirname(__file__), dir))
        dfile = os.path.join(os.path.dirname(__file__), dir+"%s.%s" %
                             (self.printname, dt.now().strftime("%Y-%m-%d=%H:%M")))
        return dfile

    @property
    def printname(self):
        return self.__class__.__name__

    def save(self, filepath=None):
        if filepath is None:
            filepath = self.getdefaultsavepath() + ".auto"
        with open(filepath, "w") as f:
            pkl.dump(self, f)
        return filepath

    def freeze(self):
        return pkl.dumps(self)

    @staticmethod
    def unfreeze(dumps):
        return pkl.loads(dumps)

    @staticmethod
    def load(filepath):
        with open(filepath) as f:
            ret = pkl.load(f)
        return ret

    @property
    def autosave(self): # for saving after each iter
        self._autosave = True
        return self


if __name__ == "__main__":
    a, b, c = loadlexidtsv("../data/freebase/labelsrevlex.map.id.tsv")
    print "loaded"
    pkl.dump((a, b, c), open("../My Passport/data/freebase/labelsrevlex.map.id.tsv.pkl", "w"))
    print "dumped"
    a, b, c = loadlexidtsv("../My Passport/data/freebase/aliasrevlex.map.id.tsv")
    pkl.dump((a, b, c), open("../My Passport/data/freebase/aliasrevlex.map.id.tsv.pkl", "w"))