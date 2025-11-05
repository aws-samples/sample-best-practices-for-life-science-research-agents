from mcp.server.fastmcp import FastMCP

mcp = FastMCP(host="0.0.0.0", stateless_http=True)

@mcp.tool()
def getPatient() -> int:
    """Get a patient"""
    return 123

@mcp.tool()
def updatePatient(patientId: int) -> int:
    """Update existing patient"""
    return 456

if __name__ == "__main__":
    mcp.run(transport="streamable-http")
