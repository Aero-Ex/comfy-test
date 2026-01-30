"""Pool management commands for comfy-test CLI."""

import sys


def cmd_pool(args) -> int:
    """Manage container pool for faster Linux testing."""
    from ..container_pool import ContainerPool

    if not args.pool_cmd:
        print("Usage: ct pool {start|stop|status}", file=sys.stderr)
        return 1

    size = getattr(args, 'size', 2)
    pool = ContainerPool(size=size)

    if args.pool_cmd == "start":
        pool.start()
    elif args.pool_cmd == "stop":
        pool.stop()
    elif args.pool_cmd == "status":
        status = pool.status()
        print(f"Pool: {status['ready']}/{status['target_size']} ready")
        if status['containers']:
            for cid in status['containers']:
                print(f"  - {cid}")
        else:
            print("  (no containers)")
    return 0


def add_pool_parser(subparsers):
    """Add the pool subcommand parser."""
    pool_parser = subparsers.add_parser(
        "pool",
        help="Manage container pool for faster Linux testing",
    )
    pool_sub = pool_parser.add_subparsers(dest="pool_cmd")
    pool_start = pool_sub.add_parser("start", help="Start the container pool")
    pool_start.add_argument(
        "--size", "-n",
        type=int,
        default=2,
        help="Number of containers to keep ready (default: 2)",
    )
    pool_sub.add_parser("stop", help="Stop and destroy all pool containers")
    pool_sub.add_parser("status", help="Show pool status")
    pool_parser.set_defaults(func=cmd_pool)
