from unittest import TestCase
from teafacto.blocks.seq.rnn import RecStack, MakeRNU
from teafacto.blocks.seq.rnu import LSTM, GRU
import numpy as np


class TestRecStack(TestCase):
    def test_get_init_info_shapes(self):
        layers = [
            GRU(dim=20, innerdim=30, param_init_states=True),
            LSTM(dim=30, innerdim=40, param_init_states=True)
        ]
        s = RecStack(*layers)
        initinfo = s.get_init_info(5)
        print initinfo
        values = [ii.eval() for ii in initinfo]
        self.assertEqual([(5, 30), (5, 40), (5, 40)], [value.shape for value in values])
        self.assertFalse(np.allclose(np.zeros_like(values[0]), values[0]))
        self.assertTrue(np.allclose(np.zeros_like(values[1]), values[1]))
        self.assertFalse(np.allclose(np.zeros_like(values[2]), values[2]))  # param init in LSTM
        for i in range(values[0].shape[0] - 1):     # repeated param init in GRU
            self.assertTrue(np.allclose(values[0][i, :], values[0][i+1, :]))
        for i in range(values[2].shape[0] - 1):  # repeated param init in LSTM
            self.assertTrue(np.allclose(values[2][i, :], values[2][i + 1, :]))

