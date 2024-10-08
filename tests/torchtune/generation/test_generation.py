# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

import pytest
import torch

from tests.test_utils import fixed_init_model
from torchtune.generation._generation import generate, sample

from torchtune.models.llama2 import llama2


class TestTextGenerate:
    """
    Test class for text generation functionality.
    """

    @pytest.fixture
    def generation_model(self, dtype=torch.float32):
        model = llama2(
            vocab_size=4_000,
            embed_dim=128,
            num_layers=2,
            num_heads=4,
            num_kv_heads=4,
            max_seq_len=2048,
        )
        fixed_init_model(model)
        model.setup_caches(batch_size=1, dtype=dtype)
        model.eval()
        return model

    @pytest.fixture
    def generation_model_no_kv_cache(self, dtype=torch.float32):
        model = llama2(
            vocab_size=4_000,
            embed_dim=128,
            num_layers=2,
            num_heads=4,
            num_kv_heads=4,
            max_seq_len=2048,
        )
        fixed_init_model(model)
        model.eval()
        return model

    @pytest.fixture
    def generation_model_batched(self, dtype=torch.float32):
        model = llama2(
            vocab_size=4_000,
            embed_dim=128,
            num_layers=2,
            num_heads=4,
            num_kv_heads=4,
            max_seq_len=2048,
        )
        fixed_init_model(model)
        model.setup_caches(batch_size=2, dtype=dtype)
        model.eval()
        return model

    @pytest.fixture
    def prompt_tokens(self):
        """
        Pytest fixture to create a list of prompt tokens for testing.
        """
        return torch.arange(2, 10)

    @pytest.fixture
    def prompt_tokens_batched(self):
        """
        Pytest fixture to create a list of prompt tokens for testing.
        """
        return torch.arange(2, 10).repeat(2, 1)

    def test_sample_consistency(self):
        """
        Test token sampling produces the right output.
        """
        # set all probabilities except for token_id=100 to 0
        logits = torch.zeros(2000)
        logits[100] = 1

        token = sample(logits, temperature=1, top_k=1)
        assert token.item() == 100

    @pytest.mark.parametrize(
        "model1,model2,prompt",
        [
            ("generation_model", "generation_model", "prompt_tokens"),
            ("generation_model", "generation_model_no_kv_cache", "prompt_tokens"),
            (
                "generation_model_batched",
                "generation_model_batched",
                "prompt_tokens_batched",
            ),
            (
                "generation_model_batched",
                "generation_model_no_kv_cache",
                "prompt_tokens_batched",
            ),
        ],
    )
    def test_reproducibility(self, request, model1, model2, prompt):
        """
        Test to check if the `generate` function produces the same output when run with the same
        inputs and a fixed seed. This should work regardless of batched input or kv cache.
        """

        model1 = request.getfixturevalue(model1)
        model2 = request.getfixturevalue(model2)
        prompt = request.getfixturevalue(prompt)

        temperature = 0.6
        top_k = 100

        torch.manual_seed(42)
        outputs_first = generate(
            model=model1,
            prompt=prompt,
            max_generated_tokens=10,
            temperature=temperature,
            top_k=top_k,
        )

        torch.manual_seed(42)
        outputs_second = generate(
            model=model2,
            prompt=prompt,
            max_generated_tokens=10,
            temperature=temperature,
            top_k=top_k,
        )

        assert outputs_first == outputs_second

    def test_batched_generate(self, generation_model_batched, prompt_tokens_batched):
        """Test batched generation works as expected."""
        temperature = 0.6
        top_k = 100

        torch.manual_seed(42)

        output = generate(
            model=generation_model_batched,
            prompt=prompt_tokens_batched,
            max_generated_tokens=10,
            temperature=temperature,
            top_k=top_k,
        )

        # The numbers here are the first 10 tokens generated by the model
        # with constantly initialized weights, a tensor input with range 2 through 10,
        # and the manual seed set to 42. They do not correspond to "recognizable" tokens.
        expected_output = [
            [
                2,
                3,
                4,
                5,
                6,
                7,
                8,
                9,
                3987,
                3991,
                3953,
                3957,
                3983,
                3964,
                3928,
                3932,
                3986,
                3982,
            ],
            [
                2,
                3,
                4,
                5,
                6,
                7,
                8,
                9,
                3958,
                3979,
                3934,
                3945,
                3993,
                3904,
                3950,
                3988,
                3948,
                3999,
            ],
        ]

        assert output == expected_output

    def test_stop_tokens(self, generation_model, prompt_tokens):
        """
        Test to check if the `generate` function produces the right output when stop tokens are
        provided.
        """
        temperature = 0.6
        top_k = 100

        # This is the first token generated by the model
        # so it should stop immediately
        stop_tokens = [3987]

        torch.manual_seed(42)

        outputs = generate(
            model=generation_model,
            prompt=prompt_tokens,
            max_generated_tokens=10,
            temperature=temperature,
            top_k=top_k,
            stop_tokens=stop_tokens,
        )

        expected_output = [[2, 3, 4, 5, 6, 7, 8, 9, 3987]]

        assert outputs == expected_output

    def test_stop_tokens_batched(self, generation_model_batched, prompt_tokens_batched):
        """
        Test to check if the `generate` function produces the right output when stop tokens are
        provided, but this time in batched format.
        """
        temperature = 0.6
        top_k = 100

        # This is the first token generated by the model
        # so it should stop immediately
        stop_tokens = [3987, 3958]

        torch.manual_seed(42)

        outputs = generate(
            model=generation_model_batched,
            prompt=prompt_tokens_batched,
            max_generated_tokens=10,
            temperature=temperature,
            top_k=top_k,
            stop_tokens=stop_tokens,
        )

        expected_output = [
            [2, 3, 4, 5, 6, 7, 8, 9, 3987],
            [2, 3, 4, 5, 6, 7, 8, 9, 3958],
        ]

        assert outputs == expected_output

    def test_stop_tokens_batched_uneven_stopping(
        self, generation_model_batched, prompt_tokens_batched
    ):
        """
        Test to check if the `generate` function produces the right output when stop tokens are
        provided, but this time in batched format. This time, seq 0 should hit a stop token before seq 1.
        We expect the output to be the length of seq 1, but the first seq should be truncated.
        """
        temperature = 0.6
        top_k = 100

        # This is the first token generated by the model
        # so it should stop immediately
        stop_tokens = [3987, 3979]

        torch.manual_seed(42)

        outputs = generate(
            model=generation_model_batched,
            prompt=prompt_tokens_batched,
            max_generated_tokens=10,
            temperature=temperature,
            top_k=top_k,
            stop_tokens=stop_tokens,
        )

        expected_output = [
            [2, 3, 4, 5, 6, 7, 8, 9, 3987, 0],
            [2, 3, 4, 5, 6, 7, 8, 9, 3958, 3979],
        ]

        assert outputs == expected_output
