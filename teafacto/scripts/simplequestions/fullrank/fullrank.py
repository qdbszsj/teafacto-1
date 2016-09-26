from teafacto.util import ticktock, argprun
import os, pickle
from teafacto.procutil import *
from IPython import embed
from scipy import sparse

from teafacto.blocks.lang.wordvec import Glove, WordEmb
from teafacto.blocks.lang.sentenc import TwoLevelEncoder
from teafacto.blocks.seq.rnn import RNNSeqEncoder
from teafacto.blocks.seq.enc import SimpleSeq2Vec
from teafacto.blocks.cnn import CNNSeqEncoder
from teafacto.blocks.basic import VectorEmbed
from teafacto.blocks.memory import MemVec
from teafacto.blocks.match import SeqMatchScore, CosineDistance

from teafacto.core.base import Block, tensorops as T


def readdata(p="../../../../data/simplequestions/clean/datamat.word.fb2m.pkl",
             entinfp="../../../../data/simplequestions/clean/subjs-counts-labels-types.fb2m.tsv",
             cachep=None, #"subjpredcharns.readdata.cache.pkl",
             maskid=-1,
             ):
    tt = ticktock("dataloader")
    if cachep is not None and os.path.isfile(cachep):      # load
        tt.tick("loading from cache")
        ret = pickle.load(open(cachep))
        tt.tock("loaded from cache")
    else:
        tt.tick("loading datamat")
        x = pickle.load(open(p))
        tt.tock("datamat loaded")
        worddic = x["worddic"]
        entdic = x["entdic"]
        entmat = x["entmat"]
        numents = x["numents"]
        traindata, traingold = x["train"]
        validdata, validgold = x["valid"]
        testdata, testgold = x["test"]
        traingold[:, 1] -= numents
        validgold[:, 1] -= numents
        testgold[:, 1] -= numents

        rwd = {v: k for k, v in worddic.items()}

        subjdic = {k: v for k, v in entdic.items() if v < numents}
        reldic = {k: v - numents for k, v in entdic.items() if v >= numents}

        subjmat = entmat[:numents]
        relmat = entmat[numents:]

        traindata = wordmat2wordchartensor(traindata, rwd=rwd, maskid=maskid)
        validdata = wordmat2wordchartensor(validdata, rwd=rwd, maskid=maskid)
        testdata = wordmat2wordchartensor(testdata, rwd=rwd, maskid=maskid)

        subjmat = wordmat2charmat(subjmat, rwd=rwd, maskid=maskid, maxlen=75)

        ret = ((traindata, traingold), (validdata, validgold),
               (testdata, testgold), (subjmat, relmat), (subjdic, reldic),
               worddic)
        if cachep is not None:
            tt.tick("dumping to cache")
            pickle.dump(ret, open(cachep, "w"))
            tt.tock("dumped to cache")

    subjinfo = loadsubjinfo(entinfp, subjdic)
    testsubjcans = loadsubjtestcans()
    testrelcans = loadreltestcans(testgold,subjdic, reldic)
    return ret + (subjinfo, (testsubjcans, testrelcans))


def loadreltestcans(testgold, subjdic, reldic, relsperentp="../../../../data/simplequestions/allrelsperent.dmp"):
    tt = ticktock("test rel can loader")
    testsubjs = testgold[:, 0]
    relsoftestsubjs = {k: ([], []) for k in set(list(testsubjs))}
    tt.tick("loading rel test cans")
    for line in open(relsperentp):
        subj, relsout, relsin = line[:-1].split("\t")
        if subj in subjdic and subjdic[subj] in relsoftestsubjs:
            relsoftestsubjs[subjdic[subj]] = (
                [reldic[x] for x in relsout.split(" ")] if relsout != "" else [],
                [reldic[x] for x in relsin.split(" ")] if relsin != "" else []
            )
    tt.tock("test cans loaded")
    relsoftestexamples = [(relsoftestsubjs[x][0], relsoftestsubjs[x][1])
                          for x in testsubjs]
    return relsoftestexamples


def loadsubjtestcans(p="../../../../data/simplequestions/clean/testcans.pkl"):
    tt = ticktock("test subjects candidate loader")
    tt.tick("loading candidates")
    ret = pickle.load(open(p))
    tt.tock("canddiates loaded")
    return ret


def loadsubjinfo(entinfp, entdic, cachep=None):#"subjinfo.cache.pkl"):
    tt = ticktock("subjinfoloader")
    def make():
        tt.tick("making subject info from file")
        subjinf = {}
        c = 0
        for line in open(entinfp):
            subjuri, subjc, objc, subjname, typuri, typname = line[:-1].split("\t")
            subjinf[entdic[subjuri]] = (subjname, typname.lower().split(), typuri, subjc, objc)
            if c % 1000 == 0:
                tt.live(str(c))
            c += 1
        tt.tock("made subject info from file")
        return subjinf
    if cachep is not None:
        if os.path.isfile(cachep):      # load
            tt.tick("loading cached subject info")
            subjinfo = pickle.load(open(cachep))
            tt.tock("loaded cached subject info")
        else:                           # make  and dump
            subjinfo = make()
            tt.tick("dumping subject info in cache")
            pickle.dump(subjinfo, open(cachep, "w"))
            tt.tock("dumped subject info in cache")
    else:       # just make
        subjinfo = make()
    return subjinfo


def buildrelsamplespace(entmat, wd, maskid=-1):
    tt = ticktock("samplespace")
    tt.tick("making sample space")
    #rwd = {v: k for k, v in wd.items()}
    entmatm = sparse.dok_matrix((entmat.shape[0], np.max(entmat) + 1))
    posblacklist = {0: {wd["base"], wd["user"]}}
    blacklist = set([wd[x] for x in "default domain of by the in at s this for with type".split()])
    #revin = {k: set() for k in np.unique(entmat)}
    #revinm = sparse.dok_matrix((np.max(entmat), entmat.shape[0]))
    samdic = {k: set() for k in range(entmat.shape[0])}     # from ent ids to sets of ent ids
    #samdic = np.zeros((entmat.shape[0], entmat.shape[0]))
    for i in range(entmat.shape[0]):
        for j in range(entmat.shape[1]):
            w = entmat[i, j]
            if w == -1:     # beginning of padding
                break
            if j in posblacklist:
                if w in posblacklist[j]:
                    continue
            if w in blacklist:
                continue
            entmatm[i, w] = 1
            #for oe in revin[w]:     # other entities already in revind
            #    samdic[oe].add(i)
            #    samdic[i].add(oe)
            #revin[w].add(i)
            #revinm[w, i] = 1
    samdicm = entmatm.dot(entmatm.T)
    for i in range(samdicm.shape[0]):
        samdic[i] = list(np.argwhere(samdicm[i, :])[:, 1])
    tt.tock("made sample space")
    return samdic, entmatm.T


class LeftBlock(Block):
    def __init__(self, inner, **kw):
        super(LeftBlock, self).__init__(**kw)
        self.inner = inner

    def apply(self, x):
        # idxs^(batsize, seqlen, ...) --> (batsize, seqlen, 2, encdim)
        res = self.inner(x).dimshuffle(0, 1, 'x', 2)
        ret = T.concatenate([res, res], axis=2)
        return ret


class RightBlock(Block):
    def __init__(self, a, b, **kw):
        super(RightBlock, self).__init__(**kw)
        self.subjenc = a
        self.predenc = b

    def apply(self, x):  # idxs^(batsize, 2)
        aret = self.subjenc(x[:, 0]).dimshuffle(0, 1, 'x', 2)
        bret = self.predenc(x[:, 1]).dimshuffle(0, 1, 'x', 2)
        ret = T.concatenate([aret, bret], axis=2)
        return ret


def run(closenegsam=False,
        checkdata=False,
        glove=False,
        embdim=100,
        charencdim=100,
        charembdim=50,
        encdim=200,
        decdim=200,
        bidir=False,
        charenc="cnn",  # "cnn" or TODO
        ):
    tt = ticktock("script")
    tt.tick("loading data")
    (traindata, traingold), (validdata, validgold), (testdata, testgold), \
    (subjmat, relmat), (subjdic, reldic), worddic, \
    subjinfo, (testsubjcans, testrelcans) = readdata()

    if closenegsam:
        relsamplespace, revind = buildrelsamplespace(relmat, worddic)
    tt.tock("data loaded")

    if checkdata:
        embed()

    numwords = max(worddic.values()) + 1
    numsubjs = max(subjdic.values()) + 1
    numrels = max(reldic.values()) + 1
    maskid = -1
    numchars = 256

    # defining model
    if glove:
        wordemb = Glove(embdim).adapt(worddic)
    else:
        wordemb = WordEmb(dim=embdim, indim=numwords)
    if charenc == "cnn":
        print "using CNN char encoder"
        charemb = VectorEmbed(indim=numchars, dim=charembdim)
        charenc = CNNSeqEncoder(inpemb=charemb,
                                innerdim=[charencdim]*2, maskid=maskid,
                                stride=1)
        wordenc = RNNSeqEncoder(inpemb=False, inpembdim=wordemb.outdim + charencdim,
                                innerdim=encdim, bidir=bidir).maskoptions(MaskMode.NONE)
        question_encoder = TwoLevelEncoder(l1enc=charenc, l2emb=wordemb,
                                           l2enc=wordenc, maskid=maskid)
    elif charenc == "rnn":
        raise NotImplementedError("rnn not implemented yet")
    else:
        raise Exception("no other modes available")

    predemb = MemVec(SimpleSeq2Vec(inpemb=wordemb,
                                   innerdim=decdim,
                                   maskid=maskid,
                                   bidir=bidir,
                                   layers=1))
    predemb.load(relmat)

    subjemb = MemVec(SimpleSeq2Vec(inpemb=charemb,
                                   innerdim=decdim,
                                   maskid=maskid,
                                   bidir=bidir,
                                   layers=2))
    subjemb.load(subjmat)

    lb = LeftBlock(question_encoder)
    rb = RightBlock(subjemb, predemb)

    scorer = SeqMatchScore(lb, rb, scorer=CosineDistance())


if __name__ == "__main__":
    argprun(run)