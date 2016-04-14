from unittest import TestCase
from teafacto.blocks.kgraph.fbencdec import FBBasicCompositeEncoder, FBSeqCompositeEncDec, FBSeqCompositeEncMemDec
import numpy as np


class TestFBBasicCompositeEncoder(TestCase):
    def test_output_shape(self):
        batsize = 100
        wordembdim = 50
        wordencdim = 20
        innerdim = 40
        datanuments = 77
        vocnumwords = 100
        numchars = 10
        wseqlen = 3
        cseqlen = 5

        m = FBBasicCompositeEncoder(
            wordembdim=wordembdim,
            wordencdim=wordencdim,
            innerdim=innerdim,
            outdim=datanuments,
            numchars=numchars,
            numwords=vocnumwords,
            glovepath="../../../data/glove/miniglove.%dd.txt",
        )

        worddata = np.random.randint(0, vocnumwords, (batsize, wseqlen, 1))
        chardata = np.random.randint(0, numchars, (batsize, wseqlen, cseqlen))
        data = np.concatenate([worddata, chardata], axis=2)

        predshape = m.predict(data).shape
        self.assertEqual(predshape, (batsize, datanuments))


class TestFBSeqCompositeEncDec(TestCase):
    def test_output_shape(self):
        batsize = 100
        wordembdim = 50
        wordencdim = 20
        innerdim = 40
        datanuments = 77
        vocnumwords = 100
        numchars = 10
        wseqlen = 3
        cseqlen = 5
        entembdim = 50
        eseqlen = 2

        m = FBSeqCompositeEncDec(
            wordembdim=wordembdim,
            wordencdim=wordencdim,
            entembdim=entembdim,
            innerdim=innerdim,
            outdim=datanuments,
            numchars=numchars,
            numwords=vocnumwords,
            glovepath="../../../data/glove/miniglove.%dd.txt",
        )

        worddata = np.random.randint(0, vocnumwords, (batsize, wseqlen, 1))
        chardata = np.random.randint(0, numchars, (batsize, wseqlen, cseqlen))
        data = np.concatenate([worddata, chardata], axis=2)
        outdata = np.random.randint(0, datanuments, (batsize, eseqlen))

        predshape = m.predict(data, outdata).shape
        print predshape
        self.assertEqual(predshape, (batsize, eseqlen, datanuments))


class TestFBSeqCompositeEncMemDec(TestCase):
    def test_output_shape(self):
        batsize = 121
        wordembdim = 50
        wordencdim = 39
        innerdim = 47
        datanuments = 79
        vocnumwords = 97
        numchars = 11
        wseqlen = 3
        ewseqlen = 2
        cseqlen = 5
        entembdim = 53
        eseqlen = 2
        attdim = 117

        entencdim = innerdim

        entworddata = np.random.randint(0, vocnumwords, (datanuments, ewseqlen, 1))
        entchardata = np.random.randint(0, numchars, (datanuments, ewseqlen, cseqlen))
        entlexdata = np.concatenate([entworddata, entchardata], axis=2)
        entdata = np.arange(0, datanuments)
        print entdata.shape, entlexdata.shape
        memdata = [entdata, entlexdata]

        m = FBSeqCompositeEncMemDec(
            wordembdim=wordembdim,
            wordencdim=wordencdim,
            entembdim=entembdim,
            innerdim=innerdim,
            outdim=datanuments,
            numchars=numchars,
            numwords=vocnumwords,
            glovepath="../../../data/glove/miniglove.%dd.txt",
            memdata=memdata,
            attdim=attdim
        )

        worddata = np.random.randint(0, vocnumwords, (batsize, wseqlen, 1))
        chardata = np.random.randint(0, numchars, (batsize, wseqlen, cseqlen))
        data = np.concatenate([worddata, chardata], axis=2)
        outdata = np.random.randint(0, datanuments, (batsize, eseqlen))

        '''
        # test output shape of lexical encoder for entity names (will be used in the memory block)
        print m.memenco.predict(entlexdata).shape
        self.assertEqual(m.memenco.predict(entlexdata).shape, (datanuments, entencdim))
        # test output shape of the whole memory payload
        mempayloadpred = m.mempayload.predict(entdata, entlexdata)
        print mempayloadpred.shape
        self.assertEqual(mempayloadpred.shape, (datanuments, entencdim + entembdim))
        # test output shape and values of the memory block
        memblockidxdata = np.arange(0, datanuments)
        memblockpred = m.memblock.predict(memblockidxdata)
        print memblockpred.shape
        self.assertEqual(memblockpred.shape, (datanuments, entencdim+entembdim))
        self.assertTrue(np.allclose(mempayloadpred, memblockpred))
        #'''
        # test output shape of custom softmax output block of decoder # TODO: here is the error
        crit = np.random.random((batsize, ))
        sob = m.softmaxoutblock.layers[0]
        print sob.W.shape
        self.assertEqual(sob.W.shape, (entencdim+entembdim+innerdim, attdim))

        # test output shape of the whole
        predshape = m.predict(data, outdata).shape
        print predshape
        self.assertEqual(predshape, (batsize, eseqlen, datanuments))

