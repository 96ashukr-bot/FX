# MetaTrader terminal agents

The matching EA must run inside each client's MetaTrader terminal or Windows VPS. Broker passwords remain inside MetaTrader.

1. Create the trading account in FX SaaS and click **Provision terminal**. Copy the one-time node credential.
2. In MetaTrader, open **Tools → Options → Expert Advisors** and allow WebRequest for `https://forex.bridgesparkinnovation.com`.
3. Copy `BridgeSparkFXAgent.mq4` into `MQL4/Experts` or `BridgeSparkFXAgent.mq5` into `MQL5/Experts`.
4. Compile it in MetaEditor and attach it to one chart only. Enable AutoTrading/Algo Trading.
5. Enter `NodeCredential`. Confirm the SaaS account changes to `CONNECTED`.
6. Before live use, test open, SL, TP, exact-ticket close, rejection, reconnect, and Kill Switch on broker demo accounts.

Never reuse one node credential on two terminals.
