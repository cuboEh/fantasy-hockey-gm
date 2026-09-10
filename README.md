# Fantasy Hockey GM

A private, non-commercial fantasy hockey analytics tool being planned by an individual developer for personal use in one Yahoo Fantasy Hockey league.

## Project status

Early local development. The developer submitted a Yahoo Fantasy Sports API access application on September 10, 2026; approval is pending. There is no deployed service or Yahoo connection.

The first implemented slice is an offline scoring CLI with explicit per-stat contributions and input provenance. See [development instructions](docs/development.md) and [data-source investigation](docs/data-sources.md). Projections, real-player rankings and draft tracking are next steps.

## Intended use

The proposed tool will run locally in Python with a command-line interface and SQLite storage. Its intended user base is one person, the developer.

Planned features include league-specific draft preparation, player valuation, schedule and lineup opportunity analysis, and recommendations for roster and streaming decisions. Every recommendation should explain its inputs, assumptions, and tradeoffs.

## Requested Yahoo access

Read-only access to the developer's authorized fantasy league information:

- League settings, scoring weights, and roster positions.
- Team rosters and player position eligibility and status.
- Available players, ownership, and waiver information where supported.
- Standings, matchup scores, and transaction history where supported.

All roster changes will be made manually through Yahoo. No write access is requested, and no browser automation or scraping workaround is planned.

## Data handling

The project proposes to combine league information with permitted hockey schedules and statistics for private analysis, subject to the applicable provider agreements. Any local caching and historical retention will follow those agreements. Yahoo attribution will be included wherever required when Yahoo data is used.

Credentials, account information, league data, and private snapshots will not be published in this repository. There is no planned sale or redistribution of Yahoo data and no public application service.

## Affiliation

This is an independent personal project and is not affiliated with or endorsed by Yahoo or the NHL.
