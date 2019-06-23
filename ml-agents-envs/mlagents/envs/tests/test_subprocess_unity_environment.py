import unittest.mock as mock
from unittest.mock import Mock, MagicMock
import unittest

from mlagents.envs.subprocess_environment import *
from mlagents.envs import UnityEnvironmentException, BrainInfo


def mock_env_factory(worker_id: int):
    return mock.create_autospec(spec=BaseUnityEnvironment)


class MockEnvWorker:
    def __init__(self, worker_id, resp=None):
        self.worker_id = worker_id
        self.process = None
        self.conn = None
        self.send = Mock()
        self.recv = Mock(return_value=resp)


class SubprocessEnvironmentTest(unittest.TestCase):
    def test_environments_are_created(self):
        SubprocessEnvManager.create_worker = MagicMock()
        env = SubprocessEnvManager(mock_env_factory, 2)
        # Creates two processes
        self.assertEqual(
            env.create_worker.call_args_list,
            [mock.call(0, mock_env_factory), mock.call(1, mock_env_factory)],
        )
        self.assertEqual(len(env.envs), 2)

    def test_worker_step_resets_on_global_done(self):
        env_mock = Mock()
        env_mock.reset = Mock(return_value="reset_data")
        env_mock.global_done = True

        def mock_global_done_env_factory(worker_id: int):
            return env_mock

        mock_parent_connection = Mock()
        step_command = EnvironmentCommand("step", (None, None, None, None))
        close_command = EnvironmentCommand("close")
        mock_parent_connection.recv = Mock()
        mock_parent_connection.recv.side_effect = [step_command, close_command]
        mock_parent_connection.send = Mock()

        worker(
            mock_parent_connection, cloudpickle.dumps(mock_global_done_env_factory), 0
        )

        # recv called twice to get step and close command
        self.assertEqual(mock_parent_connection.recv.call_count, 2)

        # worker returns the data from the reset
        mock_parent_connection.send.assert_called_with(
            EnvironmentResponse("step", 0, "reset_data")
        )

    def test_reset_passes_reset_params(self):
        manager = SubprocessEnvManager(mock_env_factory, 1)
        params = {"test": "params"}
        manager.reset(params, False)
        manager.envs[0].send.assert_called_with("reset", (params, False))

    def test_reset_collects_results_from_all_envs(self):
        SubprocessEnvManager.create_worker = lambda em, worker_id, env_factory: MockEnvWorker(
            worker_id, EnvironmentResponse("reset", worker_id, worker_id)
        )
        manager = SubprocessEnvManager(mock_env_factory, 4)

        params = {"test": "params"}
        res = manager.reset(params)
        for i, env in enumerate(manager.envs):
            env.send.assert_called_with("reset", (params, True))
            env.recv.assert_called()
            # Check that the "last steps" are set to the value returned for each step
            self.assertEqual(manager.env_last_steps[i], i)
        assert(res == [0, 1, 2, 3])

    def test_step_takes_steps_for_all_envs(self):
        SubprocessEnvManager.create_worker = lambda em, worker_id, env_factory: MockEnvWorker(
            worker_id, EnvironmentResponse("step", worker_id, worker_id)
        )
        manager = SubprocessEnvManager(mock_env_factory, 2)
        steps = [
            ("a0", "m0", "t0", "v0"), ("a1", "m1", "t1", "v1")
        ]
        res = manager.step(steps)
        for i, env in enumerate(manager.envs):
            env.send.assert_called_with("step", steps[i])
            env.recv.assert_called()
            # Check that the "last steps" are set to the value returned for each step
            self.assertEqual(manager.env_last_steps[i], i)
        assert(res == [0, 1])
