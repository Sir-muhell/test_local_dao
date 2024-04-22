require("dotenv").config();
const fs = require("fs");
const algosdk = require("algosdk");

//SMART CONTRACT DEPLOYMENT
// declare application state storage (immutable)
const localInts = 4;
const localBytes = 0;
const globalInts = 19;
const globalBytes = 9;

// get accounts from mnemonic

const creatorMnemonic = ""; // INSERT MNEMONIC
const userMnemonic = ""; // INSERT MNEMONIC

const creatorAccount = algosdk.mnemonicToSecretKey(creatorMnemonic);
const userAccout = algosdk.mnemonicToSecretKey(userMnemonic);
const creatorSecret = creatorAccount.sk;
const creatorAddress = creatorAccount.addr;
const sender = userAccout.addr;

//Generate Account
const account = algosdk.generateAccount();
const secrekey = account.sk;
const mnemonic = algosdk.secretKeyToMnemonic(secrekey);

let client = new algosdk.Algodv2("", "https://testnet-api.algonode.cloud", "");

// Read Teal File
let approvalProgram = "";
let clear_state_program = "";

try {
  approvalProgram = fs.readFileSync("./fame_approval.teal", "utf8");
  clear_state_program = fs.readFileSync("./fame_clear_state.teal", "utf8");
} catch (err) {
  console.error(err);
}

// Compile Program
const compileProgram = async (client, programSource) => {
  let encoder = new TextEncoder();
  let programBytes = encoder.encode(programSource);
  let compileResponse = await client.compile(programBytes).do();
  let compiledBytes = new Uint8Array(
    Buffer.from(compileResponse.result, "base64")
  );
  // console.log(compileResponse)
  return compiledBytes;
};

// Rounds
const waitForRound = async (round) => {
  let last_round = await client.status().do();
  let lastRound = last_round["last-round"];
  console.log("Waiting for round " + lastRound);
  while (lastRound < round) {
    lastRound += 1;
    const block = await client.statusAfterBlock(lastRound).do();
    console.log("Round " + block["last-round"]);
  }
};

//CREATE APP
// create unsigned transaction
const createApp = async (
  sender,
  approvalProgram,
  clearProgram,
  localInts,
  localBytes,
  globalInts,
  globalBytes,
  app_args
) => {
  try {
    const onComplete = algosdk.OnApplicationComplete.NoOpOC;

    let params = await client.getTransactionParams().do();
    params.fee = 1000;
    params.flatFee = true;

    let txn = algosdk.makeApplicationCreateTxn(
      sender.addr,
      params,
      onComplete,
      approvalProgram,
      clearProgram,
      localInts,
      localBytes,
      globalInts,
      globalBytes,
      app_args
    );
    let txId = txn.txID().toString();
    // Sign the transaction
    let signedTxn = txn.signTxn(sender.sk);
    console.log("Signed transaction with txID: %s", txId);

    // Submit the transaction
    await client.sendRawTransaction(signedTxn).do();
    // Wait for transaction to be confirmed
    let confirmedTxn = await algosdk.waitForConfirmation(client, txId, 4);

    //Get the completed Transaction
    console.log(
      "Transaction " +
        txId +
        " confirmed in round " +
        confirmedTxn["confirmed-round"]
    );
    // display results
    let transactionResponse = await client
      .pendingTransactionInformation(txId)
      .do();
    let appId = transactionResponse["application-index"];
    console.log("Created new app-id: ", appId);
    return appId;
  } catch (err) {
    console.log(err);
  }
};

// OPTIN
// create unsigned transaction
const localOptin = async (sender, index) => {
  try {
    let params = await client.getTransactionParams().do();
    params.fee = 1000;
    params.flatFee = true;

    let txn = algosdk.makeApplicationOptInTxn(sender.addr, params, index);
    let txId = txn.txID().toString();
    // sign, send, await
    // Sign the transaction
    let signedTxn = txn.signTxn(sender.sk);
    console.log("Signed transaction with txID: %s", txId);

    // Submit the transaction
    await client.sendRawTransaction(signedTxn).do();
    // Wait for transaction to be confirmed
    const confirmedTxn = await algosdk.waitForConfirmation(client, txId, 4);
    console.log("confirmed" + confirmedTxn);

    //Get the completed Transaction
    console.log(
      "Transaction " +
        txId +
        " confirmed in round " +
        confirmedTxn["confirmed-round"]
    );
    // display results
    // display results
    let transactionResponse = await client
      .pendingTransactionInformation(txId)
      .do();
    console.log(
      "Opted-in to app-id:",
      transactionResponse["txn"]["txn"]["apid"]
    );
    if (transactionResponse["local-state-delta"] !== undefined) {
      console.log(
        "Local State updated:",
        transactionResponse["local-state-delta"]
      );
    }
  } catch (err) {
    console.log(err);
  }
};

const creatorTokenOptin = async (sender, index, asset_id) => {
  try {
    const appArgs = [];
    appArgs.push(new Uint8Array(Buffer.from("ci")));

    let foreign_assets = [];
    foreign_assets.push(asset_id);

    let params = await client.getTransactionParams().do();
    params.fee = 1000;
    params.flatFee = true;

    // create unsigned transaction
    let nptxn = algosdk.makeApplicationNoOpTxn(
      sender.addr,
      params,
      index,
      appArgs,
      undefined,
      undefined,
      foreign_assets
    );

    let txns = [nptxn];
    txns = algosdk.assignGroupID(txns);
    let signedTx4 = nptxn.signTxn(sender.sk);

    let signed = [];
    signed.push(signedTx4);

    let tx = await client.sendRawTransaction(signed).do();
    console.log("Noop + Asset Transfer Transaction : " + tx.txId);

    // Wait for transaction to be confirmed
    const confirmedTxn = await algosdk.waitForConfirmation(client, tx.txId, 4);
    console.log("confirmed" + confirmedTxn);

    //Get the completed Transaction
    console.log(
      "Transaction " +
        tx.txId +
        " confirmed in round " +
        confirmedTxn["confirmed-round"]
    );
  } catch (err) {
    console.log(err);
  }
};

const regularTokenOptIn = async (sender, index, asset_id) => {
  try {
    const appArgs = [];
    appArgs.push(new Uint8Array(Buffer.from("oi")));

    let foreign_assets = [];
    foreign_assets.push(asset_id);

    let params = await client.getTransactionParams().do();
    params.fee = 1000;
    params.flatFee = true;

    // create unsigned asset payment transaction
    let ptxn = algosdk.makePaymentTxnWithSuggestedParams(
      sender.addr,
      algosdk.getApplicationAddress(index),
      1000000,
      undefined,
      undefined,
      params
    );

    // create unsigned transaction
    let nptxn = algosdk.makeApplicationNoOpTxn(
      sender.addr,
      params,
      index,
      appArgs,
      undefined,
      undefined,
      foreign_assets
    );

    let txns = [ptxn, nptxn];
    txns = algosdk.assignGroupID(txns);
    let signedTx1 = ptxn.signTxn(sender.sk);
    let signedTx4 = nptxn.signTxn(sender.sk);

    let signed = [];
    signed.push(signedTx1);
    signed.push(signedTx4);

    let tx = await client.sendRawTransaction(signed).do();
    console.log("Noop + Asset Transfer Transaction : " + tx.txId);

    // Wait for transaction to be confirmed
    const confirmedTxn = await algosdk.waitForConfirmation(client, tx.txId, 4);
    console.log("confirmed" + confirmedTxn);

    //Get the completed Transaction
    console.log(
      "Transaction " +
        tx.txId +
        " confirmed in round " +
        confirmedTxn["confirmed-round"]
    );
  } catch (err) {
    console.log(err);
  }
};

const regularTokenOptOut = async (sender, index, asset_id) => {
  try {
    const appArgs = [];
    appArgs.push(new Uint8Array(Buffer.from("oo")));

    let foreign_assets = [];
    foreign_assets.push(asset_id);

    let params = await client.getTransactionParams().do();
    params.fee = 1000;
    params.flatFee = true;

    // create unsigned transaction
    let nptxn = algosdk.makeApplicationNoOpTxn(
      sender.addr,
      params,
      index,
      appArgs,
      undefined,
      undefined,
      foreign_assets
    );

    let txns = [nptxn];
    txns = algosdk.assignGroupID(txns);
    let signedTx4 = nptxn.signTxn(sender.sk);

    let signed = [];
    signed.push(signedTx4);

    let tx = await client.sendRawTransaction(signed).do();
    console.log("Noop + Asset Transfer Transaction : " + tx.txId);

    // Wait for transaction to be confirmed
    const confirmedTxn = await algosdk.waitForConfirmation(client, tx.txId, 4);
    console.log("confirmed" + confirmedTxn);

    //Get the completed Transaction
    console.log(
      "Transaction " +
        tx.txId +
        " confirmed in round " +
        confirmedTxn["confirmed-round"]
    );
  } catch (err) {
    console.log(err);
  }
};

const noopLocalStake = async (sender, index, asset_id, stakeAmount) => {
  try {
    const appArgs = [];
    appArgs.push(new Uint8Array(Buffer.from("ls")));
    let params = await client.getTransactionParams().do();
    params.fee = 1000;
    params.flatFee = true;

    // create unsigned asset transfer transaction
    let attxn1 = algosdk.makeAssetTransferTxnWithSuggestedParams(
      sender.addr,
      algosdk.getApplicationAddress(index),
      undefined,
      undefined,
      stakeAmount,
      undefined,
      asset_id,
      params
    );

    // create unsigned noop transaction
    let nptxn = algosdk.makeApplicationNoOpTxn(
      sender.addr,
      params,
      index,
      appArgs,
      undefined,
      undefined
    );

    let txns = [attxn1, nptxn];
    txns = algosdk.assignGroupID(txns);
    let signedTx1 = attxn1.signTxn(sender.sk);
    let signedTx4 = nptxn.signTxn(sender.sk);

    let signed = [];
    signed.push(signedTx1);
    signed.push(signedTx4);

    let tx = await client.sendRawTransaction(signed).do();
    console.log("Noop + Asset Transfer Transaction : " + tx.txId);
    console.log("Asset ID: ", asset_id);

    // Wait for transaction to be confirmed
    const confirmedTxn = await algosdk.waitForConfirmation(client, tx.txId, 4);
    console.log("confirmed" + confirmedTxn);

    //Get the completed Transaction
    console.log(
      "Transaction " +
        tx.txId +
        " confirmed in round " +
        confirmedTxn["confirmed-round"]
    );
  } catch (err) {
    console.log(err);
  }
};

const localUnstake = async (sender, index, t, amount) => {
  try {
    const appArgs = [];
    appArgs.push(
      new Uint8Array(Buffer.from("w")),
      algosdk.encodeUint64(amount)
    );
    let params = await client.getTransactionParams().do();
    params.fee = 1000;
    params.flatFee = true;

    // create unsigned asset payment transaction
    let ptxn = algosdk.makePaymentTxnWithSuggestedParams(
      sender.addr,
      algosdk.getApplicationAddress(index),
      1000000,
      undefined,
      undefined,
      params
    );

    // create unsigned noop transaction
    let nptxn = algosdk.makeApplicationNoOpTxn(
      sender.addr,
      params,
      index,
      appArgs,
      undefined,
      undefined,
      [t]
    );

    let txns = [ptxn, nptxn];
    txns = algosdk.assignGroupID(txns);
    let signedTx1 = ptxn.signTxn(sender.sk);
    let signedTx2 = nptxn.signTxn(sender.sk);

    let signed = [];
    signed.push(signedTx1);
    signed.push(signedTx2);

    let tx = await client.sendRawTransaction(signed).do();
    console.log("Noop + Asset Transfer Transaction : " + tx.txId);
    console.log("Asset ID: ", t);

    // Wait for transaction to be confirmed
    const confirmedTxn = await algosdk.waitForConfirmation(client, tx.txId, 4);
    console.log("confirmed" + confirmedTxn);

    //Get the completed Transaction
    console.log(
      "Transaction " +
        tx.txId +
        " confirmed in round " +
        confirmedTxn["confirmed-round"]
    );

    // display results
    let transactionResponse = await client
      .pendingTransactionInformation(tx.txId)
      .do();
    console.log(
      "Opted-in to app-id:",
      transactionResponse["txn"]["txn"]["apid"]
    );
    if (transactionResponse["local-state-delta"] !== undefined) {
      console.log(
        "Local State updated:",
        transactionResponse["local-state-delta"]
      );
    }
  } catch (err) {
    console.log(err);
  }
};

const payTxn = async (sender, index) => {
  try {
    let params = await client.getTransactionParams().do();
    params.fee = 1000;
    params.flatFee = true;

    // create unsigned asset payment transaction
    let ptxn = algosdk.makePaymentTxnWithSuggestedParams(
      sender.addr,
      algosdk.getApplicationAddress(index),
      1000000,
      undefined,
      undefined,
      params
    );

    let txns = [ptxn];
    txns = algosdk.assignGroupID(txns);
    let signedTx3 = ptxn.signTxn(sender.sk);

    let signed = [];
    signed.push(signedTx3);

    let tx = await client.sendRawTransaction(signed).do();
    console.log("Noop + Asset Transfer Transaction : " + tx.txId);

    // Wait for transaction to be confirmed
    const confirmedTxn = await algosdk.waitForConfirmation(client, tx.txId, 4);
    console.log("confirmed" + JSON.stringify(confirmedTxn));

    //Get the completed Transaction
    console.log(
      "Transaction " +
        tx.txId +
        " confirmed in round " +
        confirmedTxn["confirmed-round"]
    );
  } catch (err) {
    console.log(err);
  }
};

const propose = async (
  sender,
  index,
  proposal,
  proposal_type,
  receiverAmount,
  proposal_token,
  fame
) => {
  try {
    const appArgs = [];
    appArgs.push(
      new Uint8Array(Buffer.from("pr")), //noop
      new Uint8Array(Buffer.from(proposal)), //proposal
      new Uint8Array(Buffer.from(proposal_type)), //proposal type
      algosdk.encodeUint64(receiverAmount), //proposal value
      algosdk.encodeUint64(proposal_token) //proposal token to withdraw
    );
    let params = await client.getTransactionParams().do();
    params.fee = 1000;
    params.flatFee = true;

    // create unsigned noop transaction
    let nptxn = algosdk.makeApplicationNoOpTxn(
      sender.addr,
      params,
      index,
      appArgs,
      [sender.addr],
      undefined,
      [fame]
    );

    // create unsigned asset payment transaction
    let ptxn = algosdk.makePaymentTxnWithSuggestedParams(
      sender.addr,
      algosdk.getApplicationAddress(index),
      2000000,
      undefined,
      undefined,
      params
    );

    // // create unsigned asset transfer transaction
    // let attxn1 = algosdk.makeAssetTransferTxnWithSuggestedParams(
    //   sender.addr,
    //   algosdk.getApplicationAddress(index),
    //   undefined,
    //   undefined,
    //   amount,
    //   undefined,
    //   fame,
    //   params
    // );

    // let txns = [nptxn, ptxn, attxn1];
    let txns = [nptxn, ptxn];
    txns = algosdk.assignGroupID(txns);
    let signedTx1 = nptxn.signTxn(sender.sk);
    let signedTx3 = ptxn.signTxn(sender.sk);
    // let signedTx4 = attxn1.signTxn(sender.sk);

    let signed = [];
    signed.push(signedTx1);
    signed.push(signedTx3);
    // signed.push(signedTx4);

    let tx = await client.sendRawTransaction(signed).do();
    console.log("Noop + Asset Transfer Transaction : " + tx.txId);

    // Wait for transaction to be confirmed
    const confirmedTxn = await algosdk.waitForConfirmation(client, tx.txId, 4);
    console.log("confirmed" + JSON.stringify(confirmedTxn));

    //Get the completed Transaction
    console.log(
      "Transaction " +
        tx.txId +
        " confirmed in round " +
        confirmedTxn["confirmed-round"]
    );
  } catch (err) {
    console.log(err);
  }
};

const voteTxn = async (sender, index, txnType, assets, accounts, fame) => {
  try {
    const appArgs = [];
    appArgs.push(
      new Uint8Array(Buffer.from(txnType)) //noop
    );
    let params = await client.getTransactionParams().do();
    params.fee = 1000;
    params.flatFee = true;

    // create unsigned asset transfer transaction
    let attxn1 = algosdk.makeAssetTransferTxnWithSuggestedParams(
      sender.addr,
      algosdk.getApplicationAddress(index),
      undefined,
      undefined,
      1,
      undefined,
      fame,
      params
    );

    // create unsigned noop transaction
    let nptxn = algosdk.makeApplicationNoOpTxn(
      sender.addr,
      params,
      index,
      appArgs,
      accounts,
      undefined,
      assets
    );

    let txns = [attxn1];
    txns = algosdk.assignGroupID(txns);
    let signedTx1 = attxn1.signTxn(sender.sk);
    let signedTx2 = nptxn.signTxn(sender.sk);

    let signed = [];
    signed.push(signedTx1);
    // signed.push(signedTx2);

    let tx = await client.sendRawTransaction(signed).do();
    console.log("Noop Vote up + Asset Transfer Transaction : " + tx.txId);

    // Wait for transaction to be confirmed
    const confirmedTxn = await algosdk.waitForConfirmation(client, tx.txId, 4);
    console.log("confirmed" + confirmedTxn);

    //Get the completed Transaction
    console.log(
      "Transaction " +
        tx.txId +
        " confirmed in round " +
        confirmedTxn["confirmed-round"]
    );
  } catch (err) {
    console.log(err);
  }
};

const noopProposalTxn = async (sender, index, txnType, assets, accounts) => {
  try {
    const appArgs = [];
    appArgs.push(
      new Uint8Array(Buffer.from(txnType)) //noop
    );
    let params = await client.getTransactionParams().do();
    params.fee = 1000;
    params.flatFee = true;
    // create unsigned noop transaction
    let nptxn = algosdk.makeApplicationNoOpTxn(
      sender.addr,
      params,
      index,
      appArgs,
      accounts,
      undefined,
      assets
    );

    let txns = [nptxn];
    txns = algosdk.assignGroupID(txns);
    let signedTx1 = nptxn.signTxn(sender.sk);

    let signed = [];
    signed.push(signedTx1);

    let tx = await client.sendRawTransaction(signed).do();
    console.log("Noop pay transac + Asset Transfer Transaction : " + tx.txId);

    // Wait for transaction to be confirmed
    const confirmedTxn = await algosdk.waitForConfirmation(client, tx.txId, 4);
    console.log("confirmed" + confirmedTxn);

    //Get the completed Transaction
    console.log(
      "Transaction " +
        tx.txId +
        " confirmed in round " +
        confirmedTxn["confirmed-round"]
    );
  } catch (err) {
    console.log(err);
  }
};

//UPDATE
// create unsigned transaction
const update = async (
  sender,
  index,
  approvalProgram,
  clearProgram,
  app_args
) => {
  try {
    let params = await client.getTransactionParams().do();
    params.fee = 1000;
    params.flatFee = true;

    let txn = algosdk.makeApplicationUpdateTxn(
      sender.addr,
      params,
      index,
      approvalProgram,
      clearProgram,
      app_args
    );

    // sign, send, await
    let txId = txn.txID().toString();
    // Sign the transaction
    let signedTxn = txn.signTxn(sender.sk);
    console.log("Signed transaction with txID: %s", txId);

    // Submit the transaction
    await client.sendRawTransaction(signedTxn).do();
    // Wait for transaction to be confirmed
    const confirmedTxn = await algosdk.waitForConfirmation(client, txId, 4);
    console.log("confirmed" + confirmedTxn);

    //Get the completed Transaction
    console.log(
      "Transaction " +
        txId +
        " confirmed in round " +
        confirmedTxn["confirmed-round"]
    );

    // display results
    let transactionResponse = await client
      .pendingTransactionInformation(txId)
      .do();
    let appId = transactionResponse["txn"]["txn"].apid;
    console.log("Updated app-id: ", appId);
  } catch (err) {
    console.log(err);
  }
};

// CLOSE OUT
// create unsigned transaction
const closeOut = async (sender, index) => {
  try {
    let params = await client.getTransactionParams().do();
    params.fee = 1000;
    params.flatFee = true;
    let txn = algosdk.makeApplicationCloseOutTxn(sender, params, index);
    // sign, send, await
    let txId = txn.txID().toString();
    // Sign the transaction
    let signedTxn = txn.signTxn(userAccout.sk);
    console.log("Signed transaction with txID: %s", txId);

    // Submit the transaction
    await client.sendRawTransaction(signedTxn).do();
    // Wait for transaction to be confirmed
    const confirmedTxn = await algosdk.waitForConfirmation(client, txId, 4);
    console.log("confirmed" + confirmedTxn);

    //Get the completed Transaction
    console.log(
      "Transaction " +
        txId +
        " confirmed in round " +
        confirmedTxn["confirmed-round"]
    );

    // display results
    let transactionResponse = await client
      .pendingTransactionInformation(txId)
      .do();
    console.log(
      "Closed out from app-id:",
      transactionResponse["txn"]["txn"]["apid"]
    );
  } catch (err) {
    console.log(err);
  }
};

// CLEAR STATE
// create unsigned transaction
const clearState = async (sender, index) => {
  try {
    let params = await client.getTransactionParams().do();
    params.fee = 1000;
    params.flatFee = true;
    let txn = algosdk.makeApplicationClearStateTxn(sender, params, index);
    let txId = txn.txID().toString();
    // sign, send, await
    let signedTxn = txn.signTxn(userAccout.sk);
    console.log("Signed transaction with txID: %s", txId);

    // Submit the transaction
    await client.sendRawTransaction(signedTxn).do();
    // Wait for transaction to be confirmed
    const confirmedTxn = await algosdk.waitForConfirmation(client, txId, 4);
    console.log("confirmed" + confirmedTxn);

    //Get the completed Transaction
    console.log(
      "Transaction " +
        txId +
        " confirmed in round " +
        confirmedTxn["confirmed-round"]
    );

    // display results
    let transactionResponse = await client
      .pendingTransactionInformation(txId)
      .do();
    let appId = transactionResponse["txn"]["txn"].apid;
    console.log("Cleared local state for app-id: ", appId);
  } catch (err) {
    console.log(err);
  }
};

const main = async () => {
  const approval_program = await compileProgram(client, approvalProgram);
  const clear_program = await compileProgram(client, clear_state_program);

  // configure registration and voting period
  let status = await client.status().do();

  // let app_id = 403911773;
  // let app_id = 552027377;
  // let app_id = 629334474;
  // let app_id = 629975407;
  let app_id = 645149870;
  let fames = 148814612;
  let fame = 628646526;
  let usdc = 10458941;
  let test_tokens = 160880814;

  let duration = 300;
  // let proposal_fee = 5;
  let appArgs = [algosdk.encodeUint64(duration), algosdk.encodeUint64(1)];

  // 1. create new application
  // const appId = await createApp(
  //   creatorAccount,
  //   approval_program,
  //   clear_program,
  //   localInts,
  //   localBytes,
  //   globalInts,
  //   globalBytes,
  //   appArgs
  // ); // appArgs -> null
  // app_id = parseInt(appId);
  // console.log(app_id);

  //Fund the contract
  // await payTxn(creatorAccount, app_id);

  // //2. after funding, opt into assets
  // await creatorTokenOptin(creatorAccount, app_id, fame); // opt contract into fame
  // await creatorTokenOptin(creatorAccount, app_id, usdc); // opt contract into fame
  // await creatorTokenOptin(creatorAccount, app_id, fames); // opt contract into fame

  // //3. local state opt in to the contract
  // await localOptin(creatorAccount, app_id);
  // await localOptin(userAccout, app_id);

  // //4. stake, required to do most other actions
  // await noopLocalStake(userAccout, app_id, fame, 100);

  //5. unstake
  // await localUnstake(userAccout, app_id, fame, 20000);
  // console.log(readLocalState(userAccout.addr, app_id));

  //6. Try anyone opting the contract into random token
  //await regularTokenOptIn(creatorAccount, app_id, test_tokens);

  //6.5 Try opting out
  //await regularTokenOptOut(creatorAccount, app_id, test_tokens);

  //8. propose
  let proposal = "Purchase of Farm Land";
  let proposal_type = "n";
  let proposalValue = 10;
  await propose(
    userAccout,
    app_id,
    proposal,
    proposal_type,
    proposalValue,
    fames,
    fames
  );
  // console.log(await readGlobalState(app_id));

  //9. upvote
  // await new Promise((r) => setTimeout(r, 7500));
  // await voteTxn(userAccout, app_id, "u", undefined, undefined, fame);

  //10. downvote
  // await voteTxn(userAccout, app_id, "d", undefined, undefined, fame);

  //11. execute
  // await new Promise((r) => setTimeout(r, 100000));
  // await noopProposalTxn(userAccout, app_id, "x", [0], [userAccout.addr]);
};
main();
