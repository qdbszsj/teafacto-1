from teafacto.util import argprun, ticktock
import numpy as np, os, sys, math, pickle, random
import scipy.sparse as sparse
from IPython import embed
from teafacto.core.base import Val
from teafacto.blocks.basic import VectorEmbed
from teafacto.blocks.lang.wordvec import Glove, WordEmb
from teafacto.blocks.lang.sentenc import WordCharSentEnc, TwoLevelEncoder
from teafacto.blocks.seq.enc import SimpleSeq2Vec
from teafacto.blocks.seq.rnn import RNNSeqEncoder, MaskMode
from teafacto.blocks.match import CosineDistance, MatchScore
from teafacto.blocks.memory import MemVec
from teafacto.blocks.cnn import CNNSeqEncoder
from teafacto.procutil import wordmat2wordchartensor, getmatrixvaluecounts


def readdata(p="../../../../data/simplequestions/clean/datamat.word.fb2m.pkl",
             relsperentp="../../../../data/simplequestions/allrelsperent.dmp",
             wordchar=False):
    tt = ticktock("dataloader")
    tt.tick("loading datamat")
    x = pickle.load(open(p))
    tt.tock("datamat loaded")
    worddic = x["worddic"]
    entdic = x["entdic"]
    numents = x["numents"]
    entmat = x["entmat"]
    traindata, traingold = x["train"]
    validdata, validgold = x["valid"]
    testdata, testgold = x["test"]
    testsubjs = testgold[:, 0]
    testsubjsrels = {k: ([], []) for k in set(list(testsubjs))}

    if wordchar:
        traindata = wordmat2wordchartensor(traindata, worddic=worddic)
        validdata = wordmat2wordchartensor(validdata, worddic=worddic)
        testdata = wordmat2wordchartensor(testdata, worddic=worddic)

    tt.tick("loading test cans")
    for line in open(relsperentp):
        subj, relsout, relsin = line[:-1].split("\t")
        if subj in entdic and entdic[subj] in testsubjsrels:
            testsubjsrels[entdic[subj]] = (
                [entdic[x] for x in relsout.split(" ")] if relsout != "" else [],
                [entdic[x] for x in relsin.split(" ")] if relsin != "" else []
            )
    tt.tock("test cans loaded")

    # select and offset mats
    traingold = traingold[:, 1] - numents
    validgold = validgold[:, 1] - numents
    testgold = testgold[:, 1] - numents
    entmat = entmat[numents:, :]
    # select and offset entdic
    entdic = {k: v - numents for k, v in entdic.items() if v >= numents}
    # make testrelcans with new idx space
    testrelcans = [([y - numents for y in testsubjsrels[x][0]],
                    [y - numents for y in testsubjsrels[x][1]])
                   for x in testsubjs]

    return (traindata, traingold), (validdata, validgold), (testdata, testgold),\
           worddic, entdic, entmat, testrelcans


def buildsamplespace(entmat, wd, maskid=-1):
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


def run(epochs=50,
        numbats=700,
        lr=1.,
        wreg=0.000001,
        bidir=False,
        layers=1,
        embdim=200,
        encdim=400,
        decdim=400,
        negrate=1,
        margin=1.,
        hingeloss=False,
        debug=False,
        checkdata=False,
        predencode=False,
        closenegsam=False,
        glove=False,
        atleastcan=0,
        wordchar=False,
        charencmode="rnn",  # rnn or cnn
        totalrandomtest=False,
        rarewords=0,
        ):
    maskid = -1
    tt = ticktock("predpred")
    tt.tick("loading data")
    (traindata, traingold), (validdata, validgold), (testdata, testgold), \
    worddic, entdic, entmat, testsubjsrels = readdata(wordchar=wordchar)

    if closenegsam:
        revsamplespace, revind = buildsamplespace(entmat, worddic)

    tt.tock("data loaded")
    if checkdata:
        rwd = {v: k for k, v in worddic.items()}
        red = {v: k for k, v in entdic.items()}
        def pp(widxs):
            print " ".join([rwd[x] if x in rwd else "" for x in widxs])
        embed()

    numwords = max(worddic.values()) + 1
    numents = max(entdic.values()) + 1

    if rarewords > 0:
        rwd = {v: k for k, v in worddic.items()}
        print "doing rare words"
        trainwordcounts = getmatrixvaluecounts(traindata, entmat)
        stwc = sorted(trainwordcounts.items(), key=lambda (x, y): y, reverse=True)
        fstwc = filter(lambda (x, y): y > rarewords, stwc)
        redwdic = dict(zip([rwd[k] for k, v in fstwc if k != maskid and k in rwd],
                           range(1, len(fstwc)+1)))
        redwdic["<RARE>"] = 0
        #embed()
    if bidir:
        encdim = [encdim / 2] * layers
    else:
        encdim = [encdim] * layers

    # question-side model
    if glove:
        if rarewords > 0:
            raise Exception("glove with rare words currently not supported")
        wordemb = Glove(embdim).adapt(worddic)
    else:
        if rarewords > 0:
            wordemb = WordEmb(dim=embdim, worddic=redwdic).adapt(worddic)
            #embed()
        else:
            wordemb = WordEmb(dim=embdim, worddic=worddic)
    if wordchar:
        print "wordchar model"
        numchars = 256
        if charencmode == "cnn":
            print "using CNN char encoder"
            charenc = CNNSeqEncoder(indim=numchars, inpembdim=50, innerdim=[embdim]*2,
                                    maskid=maskid, stride=1)
            wordenc = RNNSeqEncoder(inpemb=False, inpembdim=wordemb.outdim+embdim,
                                    innerdim=encdim, bidir=bidir).maskoptions(MaskMode.NONE)
            question_enc = TwoLevelEncoder(l1enc=charenc, l2emb=wordemb,
                                           l2enc=wordenc, maskid=maskid)
        else:
            question_enc = WordCharSentEnc(numchars=256, charembdim=50, charinnerdim=embdim,
                                           wordemb=wordemb, wordinnerdim=encdim, maskid=maskid,
                                           bidir=bidir)
    else:
        question_enc = SimpleSeq2Vec(inpemb=wordemb,
                                     inpembdim=wordemb.outdim,
                                     innerdim=encdim,
                                     maskid=maskid,
                                     bidir=bidir,
                                     layers=layers)

    # predicate-side model
    if predencode:
        predemb = MemVec(SimpleSeq2Vec(inpemb=wordemb,
                                inpembdim=wordemb.outdim,
                                innerdim=decdim,
                                maskid=maskid,
                                bidir=bidir,
                                layers=layers)
                         )
        predemb.load(entmat)
        """
        predemb = SimpleSeq2Vec(inpemb=wordemb,
                                inpembdim=wordemb.outdim,
                                innerdim=decdim,
                                maskid=maskid,
                                bidir=bidir,
                                layers=layers)

        class PreProc(object):
            def __init__(self, entmat):
                self.f = PreProcE(entmat)

            def __call__(self, encdata, decgold):
                return (encdata, self.f(decgold)[0][0]), {}

        class PreProcE(object):
            def __init__(self, entmat):
                self.em = Val(entmat)

            def __call__(self, x):
                return (self.em[x],), {}

        transf = PreProc(entmat)
        predtransf = transf.f
        """
    else:
        predemb = VectorEmbed(numents, decdim)
        """transf = None
        predtransf = None"""

    # scoring
    scorer = MatchScore(question_enc, predemb, scorer=CosineDistance())

    class NegIdxGen(object):
        def __init__(self, rng):
            self.min = 0
            self.max = rng

        def __call__(self, datas, gold):
            predrand = np.random.randint(self.min, self.max, gold.shape)
            return datas, predrand.astype("int32")

    class NegIdxGenClose(object):
        def __init__(self, revsamsp, rng):
            self.revsamsp = revsamsp
            self.min = 0
            self.max = rng

        def __call__(self, datas, gold):
            ret = np.zeros_like(gold)
            for i in range(gold.shape[0]):
                sampleset = self.revsamsp[gold[i]]
                if len(sampleset) > 5:
                    ret[i] = random.sample(sampleset, 1)[0]
                else:
                    ret[i] = np.random.randint(self.min, self.max)
            #embed()
            return datas, ret.astype("int32")


    if hingeloss:
        obj = lambda p, n: (n - p + margin).clip(0, np.infty)
    else:
        obj = lambda p, n: n - p

    if closenegsam:
        tt.msg("using close neg sampler")
        negidxgen = NegIdxGenClose(revsamplespace, numents)
    else:
        negidxgen = NegIdxGen(numents)

    checkembschange = True
    if checkembschange:
        #embed()
        embvar = wordemb.W
        if embvar is None:
            if hasattr(wordemb, "inner"):
                embvar = wordemb.inner.W
            else:
                raise Exception("no clue where to find embedding values")
        embvals = embvar.d.get_value()
    tt.tick("training")
    nscorer = scorer.nstrain([traindata, traingold]) \
                .negsamplegen(negidxgen) \
                .negrate(negrate) \
                .objective(obj) \
                .adagrad(lr=lr).l2(wreg).grad_total_norm(1.0)\
                .validate_on([validdata, validgold])\
        .train(numbats=numbats, epochs=epochs)
    tt.tock("trained")
    if checkembschange:
        embvar = wordemb.W
        if embvar is None:
            if hasattr(wordemb, "inner"):
                embvar = wordemb.inner.W
            else:
                raise Exception("no clue where to find embedding values")
        newembvals = embvar.d.get_value()
        embschanged = not np.allclose(embvals, newembvals)
        sumsqdiff = np.sum((newembvals - embvals)**2)
        print "Embeddings {}: {} sum of square diffs"\
            .format("changed" if embschanged else "did not change", sumsqdiff)

    # evaluation
    tt.tick("evaluating")
    qenc_pred = question_enc.predict(testdata)
    scores = []
    dontembed = True
    if atleastcan > 0:
        print "ensuring at least {} cans".format(atleastcan)
    if totalrandomtest:
        print "total randomness"
    for i in range(qenc_pred.shape[0]):
        if totalrandomtest:
            cans = [testgold[i]]
        else:
            cans = testsubjsrels[i][0] #+ testsubjsrels[i][1]
        if len(cans) < atleastcan:
            extracans = list(np.random.randint(0, numents, (atleastcan+50,)))
            extracans = list(set(extracans).difference(set(cans)))
            cans = cans + extracans[:max(0, min(len(extracans), atleastcan - len(cans)))]
            #print len(cans), cans
        if not dontembed:
            embed()
        #cans = set(cans)
        #if atleastcan > 0:
        #    while len(cans) < atleastcan:
        #        rancan = np.random.randint(0, numents)
        #        if rancan not in cans:
        #            cans.add(rancan)
        #cans = list(cans)
        if len(cans) == 0:
            scores.append([(-1, -np.infty)])
            continue
        #canembs = predemb.predict.transform(predtransf)(cans)
        canembs = predemb.predict(cans)
        scoresi = scorer.s.predict(np.repeat(qenc_pred[np.newaxis, i],
                                             canembs.shape[0], axis=0),
                                   canembs)
        scores.append(zip(cans, scoresi))
        if debug:
            embed()
        tt.progress(i, qenc_pred.shape[0], live=True)
    sortedbest = [sorted(cansi, key=lambda (x, y): y, reverse=True) for cansi in scores]
    best = [sortedbesti[0][0] for sortedbesti in sortedbest]
    # Accuracy
    accuracy = np.sum(best == testgold) * 1. / testgold.shape[0]


    print("Accuracy: {}%".format(accuracy * 100))


if __name__ == "__main__":
    argprun(run)