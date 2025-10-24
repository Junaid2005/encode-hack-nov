import argparse
import asyncio

import hypersync

# Previous hard-coded example values:
# DEFAULT_POOL = "0x3e47D7B7867BAbB558B163F92fBE352161ACcb49"
# DEFAULT_TOPIC0 = "0xd78ad95fa46c994b6551d0da85fc275fe613ce37657fb8d5e3d130840159d822"
# DEFAULT_START_BLOCK = 0
# DEFAULT_END_BLOCK = 20_333_826


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Query swap event logs for a Uniswap pool within a block range.",
    )
    parser.add_argument(
        "--pool-address",
        required=True,
        help="Address of the Uniswap pool contract.",
    )
    parser.add_argument(
        "--topic0",
        required=True,
        help="Topic0 hash of the swap event signature.",
    )
    parser.add_argument(
        "--start-block",
        type=int,
        required=True,
        help="Starting block number (inclusive).",
    )
    parser.add_argument(
        "--end-block",
        type=int,
        required=True,
        help="Ending block number (exclusive).",
    )
    return parser.parse_args()


async def main(args: argparse.Namespace):
    client = hypersync.HypersyncClient(hypersync.ClientConfig())

    query = hypersync.preset_query_logs_of_event(
        args.pool_address,
        args.topic0,
        args.start_block,
        args.end_block,
    )

    print("Running the query...")
    res = await client.get(query)
    print(
        f"Query returned {len(res.data.logs)} logs matching topic {args.topic0} from contract {args.pool_address}"
    )


if __name__ == "__main__":
    # Example invocation with the previous defaults:
    # python uniswap-pool-swap-events.py --pool-address 0x3e47D7B7867BAbB558B163F92fBE352161ACcb49 \
    #   --topic0 0xd78ad95fa46c994b6551d0da85fc275fe613ce37657fb8d5e3d130840159d822 \
    #   --start-block 0 --end-block 20333826
    cli_args = parse_args()
    asyncio.run(main(cli_args))
