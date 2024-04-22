from pyteal import *
from pyteal.ast.bytes import Bytes
from pyteal_helpers import program

# CHANGE
cooldown_time = 300


def approval():
    # globals
    fame = Int(628646526)
    fame_LP = Int(628646526)  # CHANGE to actual LP token
    fames = Int(148814612)
    usdc = Int(10458941)  # CHANGE to actual usdc token

    total_stake = Bytes(
        "tl"
    )  # uint64, must keep track of total stake otherwise people can propose more than is staked

    upvotes = Bytes(
        "uv"
    )  # uint64, people want to see how many were in favor and against, store these explicitly
    dnvotes = Bytes("dv")  # uint64
    end_time = Bytes("et")  # uint64, when vote expires in unix
    duration = Bytes("r")  # uint64, increment for end time
    cooldown = Bytes("o")  # uint64, grace period
    threshold = Bytes("t")  # uint64, increment for end time
    end_creator_opt_in = Bytes("e")  # uint64, immutable
    fees = Bytes("m")  # uint64, mutable

    proposal = Bytes("p")  # bytes
    proposal_type = Bytes("pt")  # bytes
    proposal_index = Bytes(
        "pk"
    )  # uint64, an ASA ID or App ID referenced by the proposal (flexible)
    proposal_value = Bytes(
        "pv"
    )  # uint64, how much the receiver will get if the proposal passes
    proposal_address = Bytes("pd")  # bytes, partially mutable
    receiver_address = Bytes("ra")  # bytes, partially mutable, only after the end time

    # locals
    stake = Bytes("s")  # uint64
    last_vote = Bytes("lv")  # uint64
    n_votes = Bytes(
        "nv"
    )  # uint64, number of times the holder voted over all time, for voting power
    birthday = Bytes(
        "b"
    )  # uint64, timestamp of when the user became a holder, for voting power

    # scratch vars
    voting_power = ScratchVar(TealType.uint64)

    # ops
    op_upvote = Bytes("u")
    op_dnvote = Bytes("d")
    op_token_opt_in = Bytes("oi")
    op_token_opt_out = Bytes("oo")
    op_propose = Bytes("pr")
    op_local_stake = Bytes("ls")
    op_execute = Bytes("x")
    op_withdraw = Bytes("w")
    op_creator_token_opt_in = Bytes("ci")
    op_change_duration = Bytes("cd")
    op_change_threshold = Bytes("ch")
    op_pay_algo = Bytes("pa")
    op_pay_token = Bytes("n")
    op_upgrade = Bytes("a")

    # utils
    empty = Bytes("A")
    min_duration = Int(
        600
    )  # CHANGE to 600, only used for change_duration (need a fast minimum in case mass NFT withdraw)
    has_stake = App.localGet(Txn.sender(), stake) > Int(0)
    is_proposal_over = And(
        App.globalGet(proposal)
        != empty,  # might not be necessary... must be active proposal, prevents users from repeatedly calling it
        App.globalGet(end_time) < Global.latest_timestamp(),  # after vote
        App.globalGet(end_time) + App.globalGet(cooldown)
        > Global.latest_timestamp(),  # within grace period
    )
    did_proposal_pass = And(
        App.globalGet(upvotes) > App.globalGet(dnvotes),  # more up than down
        (App.globalGet(upvotes) + App.globalGet(dnvotes))
        > (
            App.globalGet(total_stake) * App.globalGet(threshold) / Int(100)
        ),  # above threshold
        # for percent threshold: (App.globalGet(upvotes)+App.globalGet(dnvotes))>(App.globalGet(threshold)*Int(420000069)/Int(1000)),  # above threshold
    )
    reset = Seq(
        [
            App.globalPut(upvotes, Int(0)),  # votes to 0
            App.globalPut(dnvotes, Int(0)),  # votes to 0
            App.globalPut(fees, Int(0)),  # fees to 0
            App.globalPut(proposal, empty),  # proposal to empty
            App.globalPut(proposal_type, empty),  # proposal to empty
            App.globalPut(proposal_index, Int(0)),  # default is algo
            # need to enforce a cooldown period, can't do this. Failed proposals must
            # App.globalPut(end_time, Global.latest_timestamp() - App.globalGet(cooldown)),  # makes sure we are past the grace period
            App.globalPut(
                receiver_address, Global.zero_address()
            ),  # remove reciever address so people can withdraw
            App.globalPut(
                proposal_address, Global.zero_address()
            ),  # remove proposal_address
        ]
    )

    # app calls
    # phase 1, initialization
    on_creation = Seq(  # no risk
        [
            Assert(
                Btoi(Txn.application_args[0]) >= Int(cooldown_time)
            ),  # make sure duration isn't too short
            App.globalPut(upvotes, Int(0)),  # initialize the vote at 0
            App.globalPut(dnvotes, Int(0)),  # initialize the vote at 0
            App.globalPut(
                duration, Btoi(Txn.application_args[0])
            ),  # initialize the duration
            App.globalPut(
                cooldown, Int(cooldown_time)
            ),  # initialize the cooldown at 1 day, with 3 day duration
            App.globalPut(proposal, empty),  # init proposal as empty
            App.globalPut(proposal_type, empty),  # init proposal as empty
            App.globalPut(
                proposal_index, Int(0)
            ),  # init proposal token as 0 by default
            App.globalPut(
                threshold, Int(30)
            ),  # minimum percent of total of votes before a proposal can be passed
            App.globalPut(total_stake, Int(0)),  # init total stake to 0
            App.globalPut(proposal_address, Global.zero_address()),
            App.globalPut(receiver_address, Global.zero_address()),
            App.globalPut(
                end_creator_opt_in, Global.latest_timestamp() + Int(3600 * 24 * 7)
            ),  # immutable, 1 week to opt in
            Approve(),
        ]
    )

    creator_token_opt_in = Seq(  # only the creator can opt in to new tokens on day 1
        [
            Assert(Txn.sender() == Global.creator_address()),
            Assert(
                Global.latest_timestamp() < App.globalGet(end_creator_opt_in)
            ),  # only for the first day
            Assert(Global.group_size() >= Int(1)),
            InnerTxnBuilder.Begin(),
            InnerTxnBuilder.SetFields(
                {
                    TxnField.type_enum: TxnType.AssetTransfer,
                    TxnField.asset_receiver: Global.current_application_address(),
                    TxnField.asset_amount: Int(0),
                    TxnField.xfer_asset: Txn.assets[
                        0
                    ],  # Must be in the assets array sent as part of the application call
                }
            ),
            InnerTxnBuilder.Submit(),
            Approve(),
        ]
    )

    contract_opt_in = Seq(  # allow anyone to opt in, create some local state variables
        [
            App.localPut(Txn.sender(), stake, Int(0)),  # initialize local stake
            App.localPut(
                Txn.sender(), last_vote, Int(0)
            ),  # initialize local time of last vote
            App.localPut(
                Txn.sender(), n_votes, Int(0)
            ),  # initialize local number of votes
            App.localPut(
                Txn.sender(), birthday, Global.latest_timestamp()
            ),  # initialize local birthday
            Approve(),
        ]
    )

    local_stake = Seq(
        [
            Assert(Gtxn[0].type_enum() == TxnType.AssetTransfer),
            Assert(Global.group_size() == Int(2)),
            Assert(
                Gtxn[0].xfer_asset() == fame
            ),  # make sure they're using the right token
            Assert(
                Gtxn[0].asset_receiver() == Global.current_application_address()
            ),  # deposit into contract
            # update stake by replacing stake with stake + asset_amount
            App.localPut(
                Txn.sender(),
                stake,
                App.localGet(Txn.sender(), stake) + Gtxn[0].asset_amount(),
            ),
            # add to total stake
            App.globalPut(
                total_stake, App.globalGet(total_stake) + Gtxn[0].asset_amount()
            ),
            Approve(),
        ]
    )

    # phase 2: proposal cycling
    # create proposal
    propose = Seq(
        # ?TODO: you could add a minimum proposal threshold, right now anyone can propose as long as they pay the fee
        [  #
            # scratch vars
            asset_balance := AssetHolding.balance(
                Global.current_application_address(), Txn.assets[0]
            ),
            # Safety Checks
            Assert(Global.group_size() == Int(2)),
            Assert(Gtxn[1].type_enum() == TxnType.Payment),
            Assert(
                Gtxn[1].amount() >= Int(2000000)
            ),  # pay 2 algo in, 1 for contract, 1 for executor
            Assert(Gtxn[1].receiver() == Global.current_application_address()),
            # only really needto check that we're past the grace_period
            # Assert(App.globalGet(proposal) == empty),  # must be empty
            Assert(
                App.globalGet(end_time) + App.globalGet(cooldown)
                < Global.latest_timestamp()
            ),  # grace period has passed
            If(
                Txn.application_args[2]
                == op_pay_algo,  # can only propose < 10% algo treasury, can fully withdraw all other tokens though (except fame)
                If(  # if proposal is "upgrade", make sure you request <= balance-minbalance, if not then make sure only 10% balance
                    Txn.application_args[1] == op_upgrade,
                    Assert(
                        Btoi(Txn.application_args[3])
                        <= Balance(Global.current_application_address())
                        - MinBalance(Global.current_application_address())
                    ),
                    Assert(
                        Btoi(Txn.application_args[3])
                        < Balance(Global.current_application_address()) / Int(10)
                    ),
                ),
            ),
            If(
                And(
                    Txn.application_args[2]
                    == op_pay_token,  # can only withdraw 10% fame at a time,
                    Or(
                        Btoi(Txn.application_args[4]) == fame,
                        Btoi(Txn.application_args[4]) == fame_LP,
                    ),
                ),
                Seq(
                    [
                        Assert(
                            Btoi(Txn.application_args[3])
                            < asset_balance.value() / Int(10)
                        ),  # less than 10% of the asset balance
                        Assert(
                            Txn.assets[0] == Btoi(Txn.application_args[4])
                        ),  # need to check because Txn.assets is the asset balance we check for
                        # check if we have enough to cover the stake
                        Assert(
                            App.globalGet(total_stake)
                            <= asset_balance.value() - Btoi(Txn.application_args[3])
                        ),  # total stake >= asset balance - request
                    ]
                ),
            ),
            If(
                And(
                    Txn.application_args[2]
                    == op_pay_token,  # can only withdraw 10% fame at a time,
                    Btoi(Txn.application_args[4]) == fames,
                ),
                Seq(
                    [
                        Assert(
                            Btoi(Txn.application_args[3])
                            < asset_balance.value() / Int(10)
                        ),  # less than 10%
                        Assert(
                            Txn.assets[0] == Btoi(Txn.application_args[4])
                        ),  # need to check because Txn.assets is the asset balance we check for
                        # check if we have enough to cover the stake
                        Assert(
                            App.globalGet(total_stake)
                            <= asset_balance.value() - Btoi(Txn.application_args[3])
                        ),  # total stake >= asset balance - request
                    ]
                ),
            ),
            If(
                And(
                    Txn.application_args[2]
                    == op_pay_token,  # can only withdraw 10% fame at a time,
                    Btoi(Txn.application_args[4]) == usdc,
                ),
                Seq(
                    [
                        Assert(
                            Btoi(Txn.application_args[3]) < Int(10000000000)
                        ),  # less than $10k
                        Assert(
                            Txn.assets[0] == Btoi(Txn.application_args[4])
                        ),  # need to check because Txn.assets is the asset balance we check for
                        # check if we have enough to cover the stake
                        Assert(
                            App.globalGet(total_stake)
                            <= asset_balance.value() - Btoi(Txn.application_args[3])
                        ),  # total stake >= asset balance - request
                    ]
                ),
            ),
            Assert(
                has_stake
            ),  # ?TODO: add a mutable proposal_threshold (need > x stake to create proposal?)
            App.globalPut(proposal, Txn.application_args[1]),  # update proposal
            App.globalPut(
                proposal_type, Txn.application_args[2]
            ),  # update proposal type to make execution easier
            App.globalPut(
                proposal_value, Btoi(Txn.application_args[3])
            ),  # set amount receiver will get if vote passes
            App.globalPut(
                proposal_index, Btoi(Txn.application_args[4])
            ),  # update proposal token to determine payout if needed
            App.globalPut(upvotes, Int(0)),  # reset upvotes in case proposal fails
            App.globalPut(dnvotes, Int(0)),  # reset dnvotes in case proposal fails
            App.globalPut(
                end_time, Global.latest_timestamp() + App.globalGet(duration)
            ),  # start new vote from now to now + duration
            App.globalPut(
                proposal_address, Txn.sender()
            ),  # specify the proposal address (temporary)
            App.globalPut(
                receiver_address, Txn.accounts[1]
            ),  # specify the receiver address (temporary)
            Approve(),
        ]
    )

    # vote on proposal
    up_px = Seq(
        [  # public
            # CHANGE? I can stake 1 token for 5 months then add a bunch and still get the bonus
            # Safety Checks
            Assert(has_stake),
            Assert(
                App.localGet(Txn.sender(), last_vote)
                < App.globalGet(end_time) - App.globalGet(duration)
            ),  # last < start means you haven't voted yet
            Assert(Global.group_size() == Int(1)),  # Updated assertion for group size
            Assert(
                Global.latest_timestamp() < App.globalGet(end_time)
            ),  # must be before vote ends
            # init scratch vars
            voting_power.store(App.localGet(Txn.sender(), stake)),
            # calculate voting power
            If(  # if
                App.localGet(Txn.sender(), n_votes) == Int(0),  # if first vote
                # then
                voting_power.store(voting_power.load() - Int(0)),  # -0% of stake
                # else
                If(  # if
                    App.localGet(Txn.sender(), n_votes)
                    >= Int(5),  # if more than 5 votes
                    # then
                    voting_power.store(
                        voting_power.load() + App.localGet(Txn.sender(), stake) / Int(2)
                    ),  # +50% stake
                    # else
                    voting_power.store(
                        voting_power.load()
                        + App.localGet(Txn.sender(), stake)
                        * App.localGet(Txn.sender(), n_votes)
                        / Int(10)
                    ),  # +10% per vote
                ),
            ),
            If(  # if
                Global.latest_timestamp()
                < App.localGet(Txn.sender(), birthday)
                + Int(2629800),  # if less than a month
                # then
                voting_power.store(voting_power.load() - Int(0)),  # -0% of stake
                # else
                If(  # if
                    Global.latest_timestamp()
                    >= App.localGet(Txn.sender(), birthday)
                    + Int(2629800 * 5),  # if 5 or more months
                    # then
                    voting_power.store(
                        voting_power.load() + App.localGet(Txn.sender(), stake) / Int(2)
                    ),  # +50% stake
                    # else
                    voting_power.store(
                        voting_power.load()
                        + App.localGet(Txn.sender(), stake)
                        * (
                            Global.latest_timestamp()
                            - App.localGet(Txn.sender(), birthday)
                        )
                        / Int(2629800 * 10)
                    ),  # +10% per month, (Global.latest_timestamp()-App.localGet(Txn.sender(), birthday))/Int(2629800) unreduced form
                ),
            ),
            # update globals
            App.globalPut(
                upvotes, App.globalGet(upvotes) + voting_power.load()
            ),  # increment vote by voting_power
            App.globalPut(fees, App.globalGet(fees) + Int(1)),  # increment fees
            # update locals
            App.localPut(
                Txn.sender(), last_vote, Global.latest_timestamp()
            ),  # update last with current time
            App.localPut(
                Txn.sender(), n_votes, App.localGet(Txn.sender(), n_votes) + Int(1)
            ),  # update total votes by 1
            Approve(),
        ]
    )

    dn_px = Seq(
        [  # public
            # Safety Checks
            Assert(has_stake),
            Assert(
                App.localGet(Txn.sender(), last_vote)
                < App.globalGet(end_time) - App.globalGet(duration)
            ),  # last < start means you haven't voted yet
            Assert(Global.group_size() == Int(1)),
            Assert(
                Global.latest_timestamp() < App.globalGet(end_time)
            ),  # must be before vote ends
            voting_power.store(App.localGet(Txn.sender(), stake)),
            # calculate voting power
            If(  # if
                App.localGet(Txn.sender(), n_votes) == Int(0),  # if first vote
                # then
                voting_power.store(voting_power.load() - Int(0)),  # -10% of stake
                # else
                If(  # if
                    App.localGet(Txn.sender(), n_votes)
                    >= Int(5),  # if more than 5 votes
                    # then
                    voting_power.store(
                        voting_power.load() + App.localGet(Txn.sender(), stake) / Int(2)
                    ),  # +50% stake
                    # else
                    voting_power.store(
                        voting_power.load()
                        + App.localGet(Txn.sender(), stake)
                        * App.localGet(Txn.sender(), n_votes)
                        / Int(10)
                    ),  # +10% per vote
                ),
            ),
            If(  # if
                Global.latest_timestamp()
                < App.localGet(Txn.sender(), birthday)
                + Int(2629800),  # if less than a month
                # then
                voting_power.store(voting_power.load() - Int(0)),
                # else
                If(  # if
                    Global.latest_timestamp()
                    >= App.localGet(Txn.sender(), birthday)
                    + Int(2629800 * 5),  # if 5 or more months
                    # then
                    voting_power.store(
                        voting_power.load() + App.localGet(Txn.sender(), stake) / Int(2)
                    ),  # +50% stake
                    # else
                    voting_power.store(
                        voting_power.load()
                        + App.localGet(Txn.sender(), stake)
                        * (
                            Global.latest_timestamp()
                            - App.localGet(Txn.sender(), birthday)
                        )
                        / Int(2629800 * 10)
                    ),  # +10% per month, (Global.latest_timestamp()-App.localGet(Txn.sender(), birthday))/Int(2629800) unreduced form
                ),
            ),
            # update globals
            App.globalPut(
                dnvotes, App.globalGet(dnvotes) + voting_power.load()
            ),  # increment vote by voting_power
            App.globalPut(fees, App.globalGet(fees) + Int(1)),  # increment fees
            # update locals
            App.localPut(
                Txn.sender(), last_vote, Global.latest_timestamp()
            ),  # update last with current time
            App.localPut(
                Txn.sender(), n_votes, App.localGet(Txn.sender(), n_votes) + Int(1)
            ),  # update total votes by 1
            Approve(),
        ]
    )

    change_duration = Seq(
        [
            Assert(
                App.globalGet(proposal_value) >= min_duration
            ),  # will be necessary if we need to mass withdraw NFTs, 10k/10min = 69 days
            Assert(
                App.globalGet(proposal_index) >= Int(1800)
            ),  # will be necessary if we need to mass withdraw NFTs, 10k/10min = 69 days
            App.globalPut(duration, App.globalGet(proposal_value)),
            App.globalPut(
                cooldown, App.globalGet(proposal_index)
            ),  # shouldn't really use the proposal_index this way, but allows you to change the cooldown cheaply
        ]
    )

    change_threshold = Seq(
        [
            Assert(
                And(  # this has to be
                    App.globalGet(proposal_value)
                    > (
                        Int(2) * App.globalGet(threshold) / Int(3)
                    ),  # can only change threshold by less than 33% up or down
                    App.globalGet(proposal_value)
                    < (Int(4) * App.globalGet(threshold) / Int(3)),
                    App.globalGet(proposal_value)
                    > Int(5),  # must be greater than ~5% of total supply
                    App.globalGet(proposal_value)
                    < Int(75),  # must be less than 75% of total supply
                )
            ),
            App.globalPut(threshold, App.globalGet(proposal_value)),
        ]
    )

    pay_algo = Seq(  # execute the pay proposal
        # close contract and send remainder balance back to creator
        # TODO: upgrade to new contract by transferring algo
        # if upvotes >= 280000046 (2*total_supply/3)
        [
            # give proposal value
            Assert(
                Txn.accounts[1] == App.globalGet(receiver_address)
            ),  # must pass in via accounts, invalid account err otherwise
            # if proposal value > 10% of balance, must check that upvotes >= 280000046 (2*total_supply/3) for extra security
            If(
                App.globalGet(proposal_value)
                > Int(1) * Balance(Global.current_application_address()) / Int(10),
                Assert(
                    App.globalGet(upvotes) >= Int(666667)
                ),  # additional threshold to prevent algo withdraws
            ),
            InnerTxnBuilder.Begin(),
            InnerTxnBuilder.SetFields(
                {
                    TxnField.type_enum: TxnType.Payment,
                    TxnField.receiver: Txn.accounts[1],
                    TxnField.amount: App.globalGet(proposal_value),
                }
            ),
            InnerTxnBuilder.Submit(),
        ]
    )

    pay_token = Seq(  # execute the pay proposal
        # close contract and send remainder balance back to creator
        [
            # give proposal value
            Assert(
                Txn.assets[0] == App.globalGet(proposal_index)
            ),  # must be the token they proposed
            Assert(
                Txn.accounts[1] == App.globalGet(receiver_address)
            ),  # must pass in via accounts, invalid account err otherwise
            InnerTxnBuilder.Begin(),
            InnerTxnBuilder.SetFields(
                {
                    TxnField.type_enum: TxnType.AssetTransfer,
                    TxnField.xfer_asset: Txn.assets[0],
                    TxnField.asset_receiver: Txn.accounts[1],
                    TxnField.asset_amount: App.globalGet(proposal_value),
                }
            ),
            InnerTxnBuilder.Submit(),
        ]
    )

    execute = Seq(
        [
            Assert(is_proposal_over),
            Assert(
                Txn.accounts[1] == App.globalGet(receiver_address)
            ),  # must pass in via accounts, invalid account err otherwise
            If(
                did_proposal_pass,  # if this,
                Seq(
                    [  # then this
                        Cond(
                            [
                                App.globalGet(proposal_type) == op_change_duration,
                                change_duration,
                            ],
                            [
                                App.globalGet(proposal_type) == op_change_threshold,
                                change_threshold,
                            ],
                            [App.globalGet(proposal_type) == op_pay_algo, pay_algo],
                            [App.globalGet(proposal_type) == op_pay_token, pay_token],
                            [
                                App.globalGet(proposal_type) != empty,
                                Seq([reset]),
                            ],  # evaluate as true
                        ),
                        # pay the proposer a small fee
                        InnerTxnBuilder.Begin(),
                        InnerTxnBuilder.SetFields(
                            {
                                TxnField.type_enum: TxnType.Payment,
                                TxnField.receiver: Txn.accounts[1],
                                TxnField.amount: App.globalGet(fees)
                                / Int(10),  # pay 10% of the fees
                            }
                        ),
                        InnerTxnBuilder.Submit(),
                        # pay the executor a small fee
                        InnerTxnBuilder.Begin(),
                        InnerTxnBuilder.SetFields(
                            {
                                TxnField.type_enum: TxnType.Payment,
                                TxnField.receiver: Txn.sender(),
                                TxnField.amount: Int(1000000),  # pay one algo back
                            }
                        ),
                        InnerTxnBuilder.Submit(),
                    ]
                ),
            ),
            reset,  # always reset after execution
            Approve(),
        ]
    )

    # public & protected
    token_opt_in = Seq(  # public, anyone can opt in as long as they pay
        [
            # users can opt into any token as long as they pay the fee
            # DAO benefits from more assets + fees, pretty much no harm I can think of from opting into too many assets
            Assert(Global.group_size() >= Int(2)),
            Assert(
                Gtxn[0].type_enum() == TxnType.Payment
            ),  # essential, DAO benefits from deposits
            Assert(Gtxn[0].amount() >= Int(1000000)),  # cover txn fees plus more
            Assert(Gtxn[0].receiver() == Global.current_application_address()),
            # must be a stake holder to opt into assets, must hold at least the proposal fee            InnerTxnBuilder.Begin(),
            InnerTxnBuilder.SetFields(
                {
                    TxnField.type_enum: TxnType.AssetTransfer,
                    TxnField.asset_receiver: Global.current_application_address(),
                    TxnField.asset_amount: Int(0),
                    TxnField.xfer_asset: Txn.assets[
                        0
                    ],  # Must be in the assets array sent as part of the application call
                }
            ),
            InnerTxnBuilder.Submit(),
            Approve(),
        ]
    )

    token_opt_out = Seq(  # anyone can do it as long as the balance is 0
        [
            # scratch vars
            asset_balance := AssetHolding.balance(
                Global.current_application_address(), Txn.assets[0]
            ),
            # Safety checks
            Assert(
                asset_balance.value() == Int(0)
            ),  # need to check that this is 0 otherwise they can rug the treasury
            # anyone can opt out the contract out of assets with 0 balance
            InnerTxnBuilder.Begin(),
            InnerTxnBuilder.SetFields(
                {
                    TxnField.type_enum: TxnType.AssetTransfer,
                    TxnField.asset_receiver: Global.current_application_address(),
                    TxnField.asset_close_to: Txn.sender(),
                    TxnField.asset_amount: Int(0),
                    TxnField.xfer_asset: Txn.assets[
                        0
                    ],  # Must be in the assets array sent as part of the application call
                }
            ),
            InnerTxnBuilder.Submit(),
            Approve(),
        ]
    )

    # local methods
    withdraw = Seq(  # let people withdraw from theirlocal stake and then they can clear
        [
            Assert(
                App.globalGet(end_time) < Global.latest_timestamp()
            ),  # only withdraw after voting phase, can leave during grace period
            If(  # if we're still in the grace period, assert sender isn't receiver. don't want someone to avoid getting stake slashed, but also don't want block receiver until next proposal clears out receiver address
                App.globalGet(end_time) + App.globalGet(cooldown)
                > Global.latest_timestamp(),  # still in grace period/vote
                Assert(
                    Txn.sender() != App.globalGet(receiver_address)
                ),  # receiver's stake is locked until execution is complete, otherwise slash_stake is impotent
            ),
            Assert(
                Gtxn[0].type_enum() == TxnType.Payment
            ),  # essential, DAO benefits from deposits
            Assert(
                Gtxn[0].amount() >= Int(1000000)
            ),  # cover txn fees plus prevents abuse
            Assert(Gtxn[0].receiver() == Global.current_application_address()),
            Assert(Btoi(Txn.application_args[1]) <= App.localGet(Txn.sender(), stake)),
            Assert(Txn.assets[0] == fame),
            InnerTxnBuilder.Begin(),
            InnerTxnBuilder.SetFields(
                {
                    TxnField.type_enum: TxnType.AssetTransfer,
                    TxnField.xfer_asset: Txn.assets[0],
                    TxnField.asset_receiver: Txn.sender(),
                    TxnField.asset_amount: Btoi(Txn.application_args[1]),
                }
            ),
            InnerTxnBuilder.Submit(),
            App.localPut(
                Txn.sender(),
                stake,
                App.localGet(Txn.sender(), stake) - Btoi(Txn.application_args[1]),
            ),  # clear local stake
            # take from total stake
            App.globalPut(
                total_stake, App.globalGet(total_stake) - Btoi(Txn.application_args[1])
            ),
            #### Update locals ( Clear all bonuses when a user unstakes)######
            App.localPut(
                Txn.sender(), birthday, Global.latest_timestamp()
            ),  # Set Birthday to latest timestamp
            App.localPut(Txn.sender(), n_votes, Int(0)),  # Set n_votes to 0
            Approve(),
        ]
    )

    return program.event(
        init=on_creation,
        opt_in=contract_opt_in,
        no_op=Cond(
            [Txn.application_args[0] == op_creator_token_opt_in, creator_token_opt_in],
            [Txn.application_args[0] == op_token_opt_in, token_opt_in],
            [Txn.application_args[0] == op_token_opt_out, token_opt_out],
            [Txn.application_args[0] == op_propose, propose],
            [Txn.application_args[0] == op_upvote, up_px],
            [Txn.application_args[0] == op_dnvote, dn_px],
            [Txn.application_args[0] == op_local_stake, local_stake],
            [Txn.application_args[0] == op_execute, execute],
            [Txn.application_args[0] == op_withdraw, withdraw],
        ),
    )


def clear():
    return Approve()


if __name__ == "__main__":
    with open("fame_approval.teal", "w") as f:
        compiled = compileTeal(approval(), mode=Mode.Application, version=6)
        f.write(compiled)

    with open("fame_clear_state.teal", "w") as f:
        compiled = compileTeal(clear(), mode=Mode.Application, version=6)
        f.write(compiled)
