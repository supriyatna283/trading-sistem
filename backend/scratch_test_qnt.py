import sys
from app.database import SessionLocal
from app.models.whale import WhaleTransaction, Wallet, WhaleDirection

db = SessionLocal()

# 1. Check known exchanges
known_exchanges = {
    "0xc6c06298d514db089934071355e5743bf21d60": "Binance Hot",
    "0xd1e08c7793af67e9d92fe308d5697fb81d3e43": "Binance Hot",
    "0xa31ee1afc51d94c2efccaa2092ad1028285549": "Binance 15",
    "0xd5293d8e347dfe59e90efd55b2956a1343963d": "Binance 16",
    "0x0707963952f2fba59dd06f2b425ace40b492fe": "Gate.io",
    "0x28c6c06298d514db089934071355e22af164f014": "Binance 14",
    "0x3f5ce5fbfe3e9af3971dd833d26ba9b5c936f0be": "Binance 1",
    "0x8894e0a0c962cb723c1976a4421c95949be2d4e3": "Binance 8",
    "0x56eddb7aa87536c09ccc2793473599fd21a8b17f": "Binance 17",
    "0x9696ef9544a94b8e622b3da59f77f54daeb5a5c7": "Binance 18",
    "0x4976a4a02f38326660d17bf34b431dc6e2eb2327": "Binance 19",
    "0x503828934d23030e7cbd8044ab87498c4d232812": "Coinbase 1",
    "0xddfabcdc4d8ffc6d5beaf154f18b778f892a0740": "Coinbase 2",
    "0x71660c4005ba85c37ccec55d0c4493e66fe775d3": "Coinbase 3",
    "0xa097e0ec96d43d85471f377286a3424292dec104": "Coinbase 4",
    "0x3cd751e6b0078be393132286c442345e5dc49699": "Coinbase Prime",
    "0x6f6c07d80d0d433ca787d552636e5d4379a5bded": "OKX",
    "0xa7efae728d2936e78bda97dc267687568dd593f3": "OKX 2",
    "0x2910543af39aba0cd09dbb2d50200b3e800a63d2": "Kraken 1",
    "0x0a869d79a7052c7f1b55a8ebafc77a68571168ef": "Kraken 2",
    "0xf89d7b9c372f2561083e747beae0bc35e7574768": "Bybit",
    "0xd6216fc19db775df9774a6e33526131da7d19a2c": "KuCoin",
    "Hyperliquid Engine": "Hyperliquid Engine",
}

exchange_wallet_ids = set()
for addr, lbl in known_exchanges.items():
    w = db.query(Wallet).filter(Wallet.address == addr).first()
    if w:
        exchange_wallet_ids.add(w.id)
        w.entity_type = "exchange"
        w.label = lbl

print("Found exchange wallet IDs:", len(exchange_wallet_ids))
db.commit()

# Test count of QNT transactions matching exchange IDs
inflow_q = db.query(WhaleTransaction).filter(
    WhaleTransaction.token_symbol == "QNT",
    WhaleTransaction.to_wallet_id.in_(exchange_wallet_ids),
    ~WhaleTransaction.from_wallet_id.in_(exchange_wallet_ids)
).count()

outflow_q = db.query(WhaleTransaction).filter(
    WhaleTransaction.token_symbol == "QNT",
    WhaleTransaction.from_wallet_id.in_(exchange_wallet_ids),
    ~WhaleTransaction.to_wallet_id.in_(exchange_wallet_ids)
).count()

print(f"QNT Inflows: {inflow_q}, Outflows: {outflow_q}")
db.close()
