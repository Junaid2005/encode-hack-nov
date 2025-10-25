import argparse
import asyncio

import hypersync
from hypersync import (
    ClientConfig,
    JoinMode,
    TransactionField,
    TransactionSelection,
)

# Previous hard-coded example values:
# DEFAULT_TX_HASH = "0x410eec15e380c6f23c2294ad714487b2300dd88a7eaa051835e0da07f16fc282"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch transaction details by transaction hash using HyperSync.",
    )
    parser.add_argument(
        "--hash",
        required=True,
        help="Transaction hash to query.",
    )
    parser.add_argument(
        "--from-block",
        type=int,
        default=0,
        help="Starting block number for the search (default: 0).",
    )
    return parser.parse_args()


async def main(args: argparse.Namespace):
    client = hypersync.HypersyncClient(ClientConfig())

    query = hypersync.Query(
        from_block=args.from_block,
        join_mode=JoinMode.JOIN_NOTHING,
        field_selection=hypersync.FieldSelection(
            transaction=[
                TransactionField.BLOCK_NUMBER,
                TransactionField.TRANSACTION_INDEX,
                TransactionField.HASH,
                TransactionField.FROM,
                TransactionField.TO,
                TransactionField.VALUE,
                TransactionField.INPUT,
            ]
        ),
        transactions=[
            TransactionSelection(
                hash=[args.hash],
            )
        ],
    )

    print("Running the query...")
    res = await client.get(query)
    print(f"Ran the query once.  Next block to query is {res.next_block}")

    if res.data.transactions:
        tx = res.data.transactions[0]
        print(tx.from_)
        print(tx.to)
    else:
        print("No transactions found for the provided hash.")


if __name__ == "__main__":
    # Example invocation mirroring previous defaults:
    # python tx-by-hash.py --hash 0x410eec15e380c6f23c2294ad714487b2300dd88a7eaa051835e0da07f16fc282
    cli_args = parse_args()
    asyncio.run(main(cli_args))
