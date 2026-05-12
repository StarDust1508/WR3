"""SolanaSealevelAnalyzer regex coverage."""

from __future__ import annotations

import pytest

from audit_engine.analyzers.solana import SolanaSealevelAnalyzer
from audit_engine.types import Severity


@pytest.mark.asyncio
async def test_detects_unchecked_account() -> None:
    src = """
    use anchor_lang::prelude::*;

    #[derive(Accounts)]
    pub struct Withdraw<'info> {
        /// CHECK: owner check omitted on purpose
        pub vault: UncheckedAccount<'info>,
    }
    """
    out = await SolanaSealevelAnalyzer().analyze(source=src)
    assert any(
        "UncheckedAccount" in f.title or "owner check" in f.title.lower() for f in out
    )


@pytest.mark.asyncio
async def test_detects_arbitrary_cpi() -> None:
    src = """
    use solana_program::program::invoke;
    pub fn proxy(ix: Instruction, accounts: &[AccountInfo]) -> ProgramResult {
        invoke(&Instruction { ..ix }, accounts)
    }
    """
    out = await SolanaSealevelAnalyzer().analyze(source=src)
    assert any(f.severity == Severity.CRITICAL and "invocation" in f.title.lower() for f in out)


@pytest.mark.asyncio
async def test_detects_bump_from_input() -> None:
    src = """
    #[derive(Accounts)]
    pub struct Use<'info> {
        #[account(
            seeds = [b"vault"],
            bump = args.user_bump,
        )]
        pub vault: Account<'info, Vault>,
    }
    """
    out = await SolanaSealevelAnalyzer().analyze(source=src)
    assert any("bump" in f.title.lower() for f in out)


@pytest.mark.asyncio
async def test_detects_unsafe_unwrap() -> None:
    src = """
    pub fn run(ctx: Context<Run>, params: Params) -> Result<()> {
        let amount = params.amount.unwrap();
        Ok(())
    }
    """
    out = await SolanaSealevelAnalyzer().analyze(source=src)
    assert any("unwrap" in f.title.lower() for f in out)


@pytest.mark.asyncio
async def test_detects_bytemuck_type_cosplay() -> None:
    src = """
    use bytemuck::from_bytes;
    fn parse(data: &[u8]) -> &Vault {
        bytemuck::from_bytes::<Vault>(data)
    }
    """
    out = await SolanaSealevelAnalyzer().analyze(source=src)
    assert any("cosplay" in f.title.lower() or "bytemuck" in f.title.lower() for f in out)


@pytest.mark.asyncio
async def test_detects_floating_dep() -> None:
    src = """
    # Cargo.toml-ish content embedded into the prompt
    [dependencies]
    solana-program = "*"
    anchor-lang = "^0.30"
    """
    out = await SolanaSealevelAnalyzer().analyze(source=src)
    assert any(f.severity == Severity.INFO and "dependency" in f.title.lower() for f in out)


@pytest.mark.asyncio
async def test_detects_duplicate_mutable_accounts() -> None:
    src = """
    #[derive(Accounts)]
    pub struct Swap<'info> {
        #[account(mut)]
        pub user_a: Account<'info, Vault>,
        #[account(mut)]
        pub user_b: Account<'info, Vault>,
    }
    """
    out = await SolanaSealevelAnalyzer().analyze(source=src)
    assert any("duplicate" in f.title.lower() or "mutable accounts" in f.title.lower() for f in out)


@pytest.mark.asyncio
async def test_ignores_comments() -> None:
    src = """
    // bytemuck::from_bytes is bad — example only, do not use
    /* let x = args.user_bump; */
    pub struct Empty {}
    """
    out = await SolanaSealevelAnalyzer().analyze(source=src)
    assert all("bump" not in f.title.lower() for f in out)
    assert all("cosplay" not in f.title.lower() for f in out)


@pytest.mark.asyncio
async def test_empty_source_returns_no_findings() -> None:
    out = await SolanaSealevelAnalyzer().analyze(source="")
    assert out == []


@pytest.mark.asyncio
async def test_clean_anchor_program_low_noise() -> None:
    """A defensively-written Anchor program should produce no critical/high
    Sealevel findings. INFO-level dep notes are still permitted."""
    src = """
    use anchor_lang::prelude::*;

    declare_id!("ABC123");

    #[program]
    pub mod vault {
        use super::*;
        pub fn deposit(ctx: Context<Deposit>, amount: u64) -> Result<()> {
            let user = &ctx.accounts.user;
            require_keys_eq!(user.key(), ctx.accounts.vault.authority);
            Ok(())
        }
    }

    #[derive(Accounts)]
    pub struct Deposit<'info> {
        #[account(mut)]
        pub vault: Account<'info, Vault>,
        pub user: Signer<'info>,
    }

    #[account]
    pub struct Vault { pub authority: Pubkey }
    """
    out = await SolanaSealevelAnalyzer().analyze(source=src)
    critical_or_high = [f for f in out if f.severity in (Severity.HIGH, Severity.CRITICAL)]
    assert len(critical_or_high) == 0
