"""Example launcer file for experiment on simulation sawyer with trpo."""

import numpy as np
import rospy

from contrib.ros.envs.sawyer import ReacherEnv
from garage.algos import TRPO
from garage.baselines import LinearFeatureBaseline
from garage.envs.util import spec
from garage.misc.instrument import run_experiment
from garage.policies import GaussianMLPPolicy

INITIAL_SIM_ROBOT_JOINT_POS = {
    'right_j0': -0.041662954890248294,
    'right_j1': -1.0258291091425074,
    'right_j2': 0.0293680414401436,
    'right_j3': 2.17518162913313,
    'right_j4': -0.06703022873354225,
    'right_j5': 0.3968371433926965,
    'right_j6': 1.7659649178699421,
}


def run_task(*_):
    """Run task function."""
    initial_goal = np.array([0.6, -0.1, 0.80])

    rospy.init_node('trpo_sim_sawyer_reacher_exp', anonymous=True)

    env = ReacherEnv(
        initial_goal,
        initial_joint_pos=INITIAL_SIM_ROBOT_JOINT_POS,
        simulated=True)

    rospy.on_shutdown(env.shutdown)

    env.initialize()

    policy = GaussianMLPPolicy(env_spec=spec(env), hidden_sizes=(32, 32))

    baseline = LinearFeatureBaseline(env_spec=spec(env))

    algo = TRPO(
        env=env,
        policy=policy,
        baseline=baseline,
        batch_size=4000,
        max_path_length=100,
        n_itr=100,
        discount=0.99,
        step_size=0.01,
        plot=False,
        force_batch_sampler=True,
    )
    algo.train()


run_experiment(
    run_task,
    n_parallel=1,
    plot=False,
)