---
name: role-search
description: Web search guidance for roles. Use when a role needs to decide whether to search the web — defines when to search, when not to, how to write effective queries, and how to present search results. Injected automatically when a role has tools available.
---

# Role Search Skill — Web Search Guidance

## When to Search

Search when you need **specific, current, or out-of-training information**:

- Library / framework / latest version (e.g. "Next.js 15 App Router docs", "Prisma v6 changelog")
- Current best practices for a specific technology
- Cloud service pricing and features (AWS, Vercel, Supabase...)
- Security vulnerabilities or CVEs related to the project stack
- Competitor analysis, market benchmarks
- Third-party API documentation

## When NOT to Search

Do not search when:
- The request only requires analysis or planning based on available information
- The user has already provided sufficient context
- The question is about internal project processes or domain-specific business logic

## How to Search Effectively

### 1. Use specific queries, not vague ones
```
Bad:  web_search(nextjs authentication)
Good: web_search(Next.js 15 App Router authentication with NextAuth v5 2025)
```

### 2. Search from multiple angles when needed
```
Step 1: web_search(Supabase vs PlanetScale pricing 2025)
Step 2: web_search(Supabase free tier limitations production)
→ Synthesize results from both queries before making a recommendation
```

### 3. Cite sources in output
When using information from search, reference the source:
```
According to the official Next.js 15 documentation (nextjs.org/docs):
- Server Actions became stable in v14
- ...
```

## Output Format After Search

After searching, synthesize the results and respond in the format appropriate for your role.
Do not list raw search results — analyze and present actionable, valuable content.
