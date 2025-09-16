#!/usr/bin/env python3
"""
Simple script to run the database seeder
"""

import asyncio
from seed_mock import MockDataSeeder

async def main():
    print("🌱 Starting database seeding...")
    seeder = MockDataSeeder()
    await seeder.seed_all()
    print("🎉 Seeding completed!")

if __name__ == "__main__":
    asyncio.run(main())
