const algosdk = require("algosdk");

const mnemonic =
  "earn divorce salad blast absurd inmate scheme laundry child art neutral upon cluster pudding hospital strike pause sleep custom orchard endorse unable mixture abstract clown";
const account = algosdk.mnemonicToSecretKey(mnemonic);
const address = account.addr;

console.log("Wallet Address:", address);
console.log("secret key :", account);

const appId = 225262568;
const appId2 = 395172418;
const appId3 = 644332780;
const appAddr = algosdk.getApplicationAddress(appId3);

console.log(`Application ID:      ${appId3}`);
console.log(`Application Address: ${appAddr}`);
