import argparse
import asyncio

import hypersync

# Previous hard-coded example values:
# DEFAULT_CONTRACT = "0xdAC17F958D2ee523a2206206994597C13D831ec7"
# DEFAULT_TOPIC0 = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
# DEFAULT_START_BLOCK = 17000000
# DEFAULT_END_BLOCK = 17000050


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch logs for a specific event from a contract within a block range.",
    )
    parser.add_argument(
        "--contract",
        required=True,
        help="Contract address to query logs from.",
    )
    parser.add_argument(
        "--topic0",
        required=True,
        help="Topic0 hash of the event signature.",
    )
    parser.add_argument(
        "--start-block",
        type=int,
        required=True,
        help="Inclusive starting block number.",
    )
    parser.add_argument(
        "--end-block",
        type=int,
        required=True,
        help="Exclusive ending block number.",
    )
    return parser.parse_args()


async def main(args: argparse.Namespace):
    client = hypersync.HypersyncClient(hypersync.ClientConfig())

    query = hypersync.preset_query_logs_of_event(
        args.contract,
        args.topic0,
        args.start_block,
        args.end_block,
    )

    print("Running the query...")
    res = await client.get(query)
    print(
        f"Query returned {len(res.data.logs)} logs of the specified event from contract {args.contract}"
    )


if __name__ == "__main__":
    # Example invocation mirroring previous defaults:
    # python simple-logs-of-event.py --contract 0xdAC17F958D2ee523a2206206994597C13D831ec7 \
    #   --topic0 0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef \
    #   --start-block 17000000 --end-block 17000050
    cli_args = parse_args()
    asyncio.run(main(cli_args))
