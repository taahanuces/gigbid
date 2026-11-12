from pathlib import Path

from agent.config import load_config
from agent.graphs.bid_graph import BidGraphServices, build_bid_graph
from agent.graphs.conversation_graph import build_conversation_graph
from mcp_servers.marketplace.adapters.memory import InMemoryMarketplaceAdapter
from rag.index.memory import InMemoryEvidenceIndex

ROOT = Path(__file__).resolve().parents[1]
IMAGES = ROOT / "docs" / "images"
DOCUMENT = ROOT / "docs" / "GRAPH_RENDERS.md"


def render() -> Path:
    marketplace = InMemoryMarketplaceAdapter()
    bid = build_bid_graph(
        BidGraphServices(
            marketplace=marketplace,
            evidence_index=InMemoryEvidenceIndex(),
            config=load_config(ROOT / "agent" / "config.yaml"),
        )
    )
    conversation = build_conversation_graph(marketplace)
    diagrams = {
        "bid_graph.mmd": bid.get_graph(xray=True).draw_mermaid(),
        "conversation_graph.mmd": conversation.get_graph(xray=True).draw_mermaid(),
    }
    IMAGES.mkdir(parents=True, exist_ok=True)
    for name, diagram in diagrams.items():
        (IMAGES / name).write_text(diagram.rstrip() + "\n", encoding="utf-8")
    DOCUMENT.write_text(
        "# LangGraph Renders\n\n"
        "Generated from the compiled graph definitions with `python scripts/render_graphs.py`. "
        "Do not edit the Mermaid blocks by hand.\n\n"
        "## Bid graph\n\n```mermaid\n"
        f"{diagrams['bid_graph.mmd'].rstrip()}\n```\n\n"
        "## Conversation graph\n\n```mermaid\n"
        f"{diagrams['conversation_graph.mmd'].rstrip()}\n```\n",
        encoding="utf-8",
    )
    return DOCUMENT


if __name__ == "__main__":
    print(render())
