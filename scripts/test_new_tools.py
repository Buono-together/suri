import asyncio
import json
from app.agents.base import list_mcp_tools, call_mcp_tool


async def main():
    print("=" * 60)
    print("TEST 1: MCP tool discovery (should show 3 tools now)")
    print("=" * 60)
    tools = await list_mcp_tools()
    for t in tools:
        print(f"  - {t['name']}")
    print(f"Total: {len(tools)} tools")
    
    print("\n" + "=" * 60)
    print("TEST 2: list_tables")
    print("=" * 60)
    result = await call_mcp_tool("list_tables", {})
    parsed = json.loads(result)
    for row in parsed.get("rows", []):
        print(f"  - {row['name']:30} [{row['type']}]  ~{row.get('row_estimate', '?')} rows")
    
    print("\n" + "=" * 60)
    print("TEST 3: describe_table(customers_safe)")
    print("=" * 60)
    result = await call_mcp_tool("describe_table", {"table_name": "customers_safe"})
    parsed = json.loads(result)
    for row in parsed.get("rows", []):
        print(f"  - {row['name']:30} {row['data_type']:20} nullable={row['is_nullable']}")
    
    print("\n" + "=" * 60)
    print("TEST 4: describe_table — SQL injection attempt (should fail)")
    print("=" * 60)
    result = await call_mcp_tool(
        "describe_table", 
        {"table_name": "customers; DROP TABLE products; --"}
    )
    parsed = json.loads(result)
    print(f"error: {parsed.get('error')}")
    print(f"type: {parsed.get('type')}")
    
    print("\n" + "=" * 60)
    print("TEST 5: describe_table — PII table (blocked by ROLE)")
    print("=" * 60)
    result = await call_mcp_tool("describe_table", {"table_name": "customers"})
    parsed = json.loads(result)
    # customers 원본은 suri_readonly 권한 없으니 information_schema가 자동 필터
    # → 빈 결과 또는 row_count=0
    print(f"row_count: {parsed.get('row_count')}")
    if parsed.get("row_count") == 0:
        print("  → customers is not visible to suri_readonly (Layer 2 works)")


asyncio.run(main())
