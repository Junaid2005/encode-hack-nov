import hypersync
import argparse
import asyncio
import time
from hypersync import LogField

# Previous hard-coded example values:
# DEFAULT_ADDRESS = "0x6B175474E89094C44Da98b954EedeAC495271d0F"
# DEFAULT_TOPIC0 = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Watch real-time logs for a specific contract and event from HyperSync.",
    )
    parser.add_argument(
        "--address",
        required=True,
        help="Contract address to watch logs for.",
    )
    parser.add_argument(
        "--topic0",
        required=True,
        help="Topic0 hash (event signature) to filter logs.",
    )
    parser.add_argument(
        "--poll-delay",
        type=float,
        default=1.0,
        help="Seconds to wait between archive height polling attempts (default: 1.0).",
    )
    return parser.parse_args()


async def main(args: argparse.Namespace):
    client = hypersync.HypersyncClient(hypersync.ClientConfig())

    height = await client.get_height()

    query = hypersync.Query(
        from_block=height,
        logs=[
            hypersync.LogSelection(
                address=[args.address],
                topics=[[args.topic0]],
            )
        ],
        field_selection=hypersync.FieldSelection(
            log=[
                LogField.DATA,
                LogField.ADDRESS,
                LogField.TOPIC0,
                LogField.TOPIC1,
                LogField.TOPIC2,
                LogField.TOPIC3,
            ]
        ),
    )

    decoder = hypersync.Decoder(
        ["Transfer(address indexed from, address indexed to, uint256 value)"]
    )

    total_volume = 0
    while True:
        res = await client.get(query)

        if res.data.logs:
            decoded_logs = await decoder.decode_logs(res.data.logs)

            for log in decoded_logs:
                if log is None:
                    continue

                total_volume += log.body[0].val

        print(f"total transfer volume is {total_volume / 1e18} tokens")

        height = res.archive_height
        while height < res.next_block:
            print(f"waiting for chain to advance. Height is {height}")
            height = await client.get_height()
            time.sleep(args.poll_delay)

        query.from_block = res.next_block


if __name__ == "__main__":
    # Example invocation with the previous defaults:
    # python watch.py --address 0x6B175474E89094C44Da98b954EedeAC495271d0F \
    #   --topic0 0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef
    cli_args = parse_args()
    asyncio.run(main(cli_args))
