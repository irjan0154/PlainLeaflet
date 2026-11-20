import pytest

from helpers import CONTRACT, Env


@pytest.fixture
def env(direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie, direct_owner):
    contract = direct_deploy(CONTRACT)
    return Env(direct_vm, contract, direct_alice, direct_bob, direct_charlie, direct_owner)
