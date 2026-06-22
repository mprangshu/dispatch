---
agent_id: fetch-userstory-ado-mcp
name: Fetch User Story (ADO MCP)
domain: requirements
tags: [user-story, azure-devops, ado, mcp, neo4j, retrieval, read-only]
autonomy_default: L2
autonomy_supported: [L2]
triggers: [manual, api]
---

## Overview
Retrieves user stories from Azure DevOps (via the ADO MCP tool) or from the Neo4j knowledge graph (via the Neo4j MCP tool) and presents them as a structured list. Built as a single `create_react_agent` that selects the appropriate source based on available credentials and the user's request. The agent performs no writes — all operations are read-only. Output is a `user-story-list` GenUI component. This agent is primarily used as an upstream step to feed other agents (e.g. Test Case Generation, Test Data Provisioning) with user stories.

## Autonomy Level
L2 · Automated.

The agent selects the data source and fetches stories autonomously. It pauses at one HITL gate to confirm the fetched list before returning it — giving the user the opportunity to filter stories or correct the query before downstream agents consume the results.

## Inputs
| Input | Required | Description |
|-------|----------|-------------|
| User Request | Yes | Natural language query, e.g. "Fetch user stories for Sprint 7 in project XYZ" |
| ADO Project | No | Azure DevOps project name; extracted from the user request or the active workspace project |
| Sprint / Iteration | No | Sprint name or iteration path to filter stories by |
| Work Item IDs | No | Specific work item IDs to fetch directly instead of querying by sprint |
| Project | Yes | Scopes the Neo4j namespace and MCP server configuration |

## Outputs
| Output | Description |
|--------|-------------|
| User Story List | Structured list of user stories with ID, title, description, acceptance criteria, and status — rendered as a `user-story-list` GenUI component |

## Triggers
| Trigger | Description |
|---------|-------------|
| Manual | Enter a retrieval request in the workspace |
| API | Submit a query or list of work item IDs programmatically |

## Deployment
**Hardware:** 1 vCPU, 2 GB RAM; no GPU required.
**Software:** Python 3.11+, LangGraph 1.0+, ADO MCP server (requires Azure DevOps Personal Access Token), Neo4j MCP server (optional fallback).

## Limitations
- Read-only agent; it does not create, update, or delete any Azure DevOps work items or Neo4j nodes.
- ADO MCP access requires a valid Personal Access Token scoped to the target ADO organisation; missing credentials fall back to Neo4j only.
- Neo4j fallback only contains user stories that were previously synced from ADO; it may be stale relative to the live ADO board.
- Large sprint backlogs (500+ stories) may be paginated; the agent returns the first page by default and prompts the user to request more.
