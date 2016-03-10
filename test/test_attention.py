from unittest import TestCase
from teafacto.blocks.attention import Attention, DummyAttentionConsumer, DummyAttentionGen
from teafacto.blocks.rnn import RNNDecoder
from teafacto.blocks.rnu import GRU
from teafacto.blocks.basic import Softmax, MatDot as Lin, IdxToOneHot
import numpy as np


class DummyAttentionGeneratorConsumerTest(TestCase):
    def setUp(self):
        criteriondim = 30
        datadim = 20
        innerdim = 25
        batsize = 33
        seqlen = 11
        self.attgenshape = (batsize, seqlen)
        self.attconshape = (batsize, datadim)
        self.attgen = DummyAttentionGen(indim=criteriondim+datadim, innerdim=innerdim)
        self.attcon = DummyAttentionConsumer()
        self.att = Attention(self.attgen, self.attcon)
        self.criterion_val = np.random.random((batsize, criteriondim))
        self.data_val = np.random.random((batsize, seqlen, datadim))

    def test_generator_shape(self):
        pred = self.attgen.predict(self.criterion_val, self.data_val)
        self.assertEqual(pred.shape, self.attgenshape)

    def test_generator_param_prop(self):
        self.attgen.predict(self.criterion_val, self.data_val)
        allparams = self.attgen.output.allparams
        self.assertSetEqual(allparams, {self.attgen.W})

    def test_consumer_shape(self):
        pred = self.att.predict(self.criterion_val, self.data_val)
        self.assertEqual(pred.shape, self.attconshape)

    def test_consumer_param_prop(self):
        self.att.predict(self.criterion_val, self.data_val)
        allparams = self.att.output.allparams
        self.assertSetEqual(allparams, {self.attgen.W})


class TestAttentionRNNDecoder(TestCase):
    def setUp(self):
        vocsize = 10
        innerdim = 50
        encdim = 30
        seqlen = 5
        batsize = 77
        self.dec = RNNDecoder(
            IdxToOneHot(vocsize),
            GRU(dim=vocsize+encdim, innerdim=innerdim),
            Lin(indim=innerdim, dim=vocsize),
            Softmax(),
            seqlen=5,
            indim=vocsize
        )
        self.att = Attention(DummyAttentionGen(indim=innerdim+encdim), DummyAttentionConsumer())
        self.dec(self.att)
        self.data = np.random.random((batsize, seqlen, encdim))

        self.predshape = (batsize, seqlen, vocsize)

    def test_shape(self):
        pred = self.dec.predict(self.data)
        self.assertEqual(pred.shape, self.predshape)

    def test_attentiongenerator_param_in_allparams(self):
        self.dec.predict(self.data)
        allparams = self.dec.output.allparams
        self.assertIn(self.att.attentiongenerator.W, allparams)
