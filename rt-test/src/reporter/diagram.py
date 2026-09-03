"""
ASCII Diagram & Provenance Trace Renderer for RT Test Results.
Generates structured node-and-arrow diagrams for RT Patterns (PT-01 to PT-08)
and dynamic graphs for raw relation assertions.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
from models.link import WebLink
from models.resource import ResourceNode

LINE_WIDTH = 140


def _status_badge(passed: bool, missing_label: str = "MISSING") -> str:
    """Return a visual PASS/FAIL badge."""
    return "[✓ PASS]" if passed else f"[✗ {missing_label}]"


def _make_box(label: str, uri: str = "", width: int = LINE_WIDTH) -> List[str]:
    """Create a fully-enclosed ASCII box of exact width."""
    inner_width = width - 4  # space for "| " and " |"
    text = f"{label}: {uri}" if uri else label
    if len(text) > inner_width:
        text = text[: inner_width - 3] + "..."
    border = "+" + "-" * (width - 2) + "+"
    content = f"| {text:<{inner_width}} |"
    return [border, content, border]


def _make_down_arrow(label: str = "", status: str = "") -> List[str]:
    """Create an aligned vertical arrow shaft."""
    lines = ["        |"]
    if label or status:
        badge = f" {status}" if status else ""
        lines.append(f"        | {label}{badge}")
    lines.append("        v")
    return lines


def _wrap_link_repr(prefix: str, link_repr: str, width: int = LINE_WIDTH, indent: str = "      ") -> List[str]:
    """Wrap long link representation across lines without exceeding max width."""
    full = f"{prefix}{link_repr}"
    if len(full) <= width:
        return [full]

    parts = link_repr.split(" -> ")
    if len(parts) >= 2:
        res = [f"{prefix}{parts[0]} ->"]
        for p in parts[1:-1]:
            res.append(f"{indent}-> {p} ->")
        res.append(f"{indent}-> {parts[-1]}")
        final_res = []
        for line in res:
            if len(line) > width:
                final_res.append(line[: width - 3] + "...")
            else:
                final_res.append(line)
        return final_res
    else:
        return [full[: width - 3] + "..."]


def _format_http_trace(
    node: Optional[ResourceNode],
    include_all_discovered: bool = True,
    matched_links: Optional[List[WebLink]] = None,
    width: int = LINE_WIDTH,
) -> str:
    """Format an HTTP call and link discovery trace for a ResourceNode."""
    if not node:
        return "  (No HTTP harvest information recorded)"

    lines = []
    status_str = f"{node.status_code} OK" if node.status_code == 200 else (f"HTTP {node.status_code}" if node.status_code > 0 else "CONNECTION ERROR")
    ct_str = node.content_type or "unknown"
    dir_cnt = len(node.direct_links)
    exp_cnt = len(node.expanded_links)
    ls_cnt = len(node.referenced_linksets)

    uri_str = node.uri
    if len(f"  * GET {uri_str}") > width:
        uri_str = uri_str[: width - 12] + "..."
    lines.append(f"  * GET {uri_str}")
    lines.append(f"    Status: {status_str} | Content-Type: {ct_str}")
    lines.append(f"    Discovered Links: {len(node.all_links)} total ({dir_cnt} direct, {exp_cnt} expanded from {ls_cnt} linkset(s))")

    if node.error:
        lines.append(f"    Error: {node.error}")

    if not include_all_discovered:
        relevant_matches = [
            ml for ml in (matched_links or [])
            if ml.anchor == node.uri or node.uri in (ml.anchor, ml.resolved_href())
        ]
        if relevant_matches:
            lines.append("    Matched Relations:")
            for idx, link in enumerate(relevant_matches, 1):
                disp = link.display_repr()
                lines.extend(_wrap_link_repr(f"      [{idx}] ", disp, width=width, indent="          "))
    else:
        if node.all_links:
            lines.append("    Discovered Relations:")
            for idx, link in enumerate(node.all_links, 1):
                disp = link.display_repr()
                lines.extend(_wrap_link_repr(f"      [{idx}] ", disp, width=width, indent="          "))

    return "\n".join(lines)


class ASCIIDiagramRenderer:
    """Renders ASCII diagrams for pattern-based and raw test results."""

    @staticmethod
    def render_assertion_result(
        result: Any,
        harvest_nodes: Optional[Dict[str, ResourceNode]] = None,
        include_trace: bool = False,
    ) -> str:
        """Render ASCII diagram (and optional HTTP trace) for a single AssertionResult or group."""
        pattern_id = getattr(result, "pattern_id", None)
        roles = getattr(result, "pattern_roles", {}) or {}
        passed = getattr(result, "passed", False)
        node = getattr(result, "harvest_node", None)
        nodes_map = dict(harvest_nodes or {})
        if node and node.uri not in nodes_map:
            nodes_map[node.uri] = node

        title_prefix = "DIAGRAM & HTTP TRACE" if include_trace else "DIAGRAM"
        header_title = f"{title_prefix}: {getattr(result, 'case_name', 'Test Case')}"
        if len(header_title) > LINE_WIDTH:
            header_title = header_title[: LINE_WIDTH - 3] + "..."

        lines = [
            "=" * LINE_WIDTH,
            header_title,
            f"Overall Status: {_status_badge(passed, 'FAILED')}",
            "-" * LINE_WIDTH,
        ]

        if pattern_id:
            raw_id = str(pattern_id).upper().replace("RT-", "").replace("PT-", "").replace("P", "").strip()
            method_name = f"_render_pt{raw_id.zfill(2)}"
            renderer_method = getattr(ASCIIDiagramRenderer, method_name, None)
            if renderer_method:
                diagram = renderer_method(roles=roles, result=result, nodes=nodes_map)
                lines.append(diagram)
            else:
                lines.append(ASCIIDiagramRenderer._render_generic(result, nodes_map))
        else:
            lines.append(ASCIIDiagramRenderer._render_generic(result, nodes_map))

        if include_trace:
            lines.append("-" * LINE_WIDTH)
            lines.append("HTTP Call Trace & Provenance:")
            matched_links = getattr(result, "matched_links", [])
            include_all = not passed
            if nodes_map:
                for uri, n in nodes_map.items():
                    lines.append(_format_http_trace(n, include_all_discovered=include_all, matched_links=matched_links))
            elif node:
                lines.append(_format_http_trace(node, include_all_discovered=include_all, matched_links=matched_links))
            else:
                lines.append("  (No HTTP harvest information available)")

        lines.append("=" * LINE_WIDTH)
        return "\n".join(lines)

    @staticmethod
    def _render_pt01(roles: Dict[str, Any], result: Any, nodes: Dict[str, ResourceNode]) -> str:
        res_uri = roles.get("resource") or getattr(result, "target_url", "Resource")
        prof_uri = roles.get("profile") or "Profile URI"
        desc_raw = roles.get("profile_description") or roles.get("description") or roles.get("profile_doc")
        desc_uri = None
        desc_type = roles.get("profile_description_type") or roles.get("description_type") or roles.get("profile_description_profile")
        if isinstance(desc_raw, str):
            desc_uri = desc_raw.strip()
        elif isinstance(desc_raw, dict):
            desc_uri = (desc_raw.get("uri") or desc_raw.get("href") or desc_raw.get("url") or "").strip()
            if not desc_type:
                desc_type = (desc_raw.get("type") or desc_raw.get("profile") or "").strip()

        type_uri = roles.get("profile_type")
        alts = roles.get("profile_alternate") or roles.get("profile_alternates") or []
        if isinstance(alts, str):
            alts = [alts]

        res_node = nodes.get(res_uri)
        prof_passed = False

        if res_node:
            prof_matches = res_node.all_links.find_links(rel="profile", target=prof_uri if prof_uri != "Profile URI" else None)
            prof_passed = len(prof_matches) > 0
        else:
            prof_passed = getattr(result, "passed", False)

        prof_node = nodes.get(prof_uri)

        diagram = []
        diagram.extend(_make_box("Resource", res_uri))
        diagram.extend(_make_down_arrow('rel="profile"', _status_badge(prof_passed)))
        diagram.extend(_make_box("Profile", prof_uri))

        if desc_uri or type_uri or alts:
            diagram.append("        |")
            if alts:
                for alt in alts:
                    alt_uri = alt if isinstance(alt, str) else alt.get("uri", alt.get("href", str(alt)))
                    alt_passed = False
                    if prof_node:
                        alt_matches = prof_node.all_links.find_links(rel="alternate", target=alt_uri)
                        alt_passed = len(alt_matches) > 0
                    badge = _status_badge(alt_passed) if prof_node else "[? UNCHECKED]"
                    a_str = f"        +---> rel=\"alternate\"   -> {alt_uri}"
                    if len(a_str) > LINE_WIDTH - 15:
                        a_str = a_str[: LINE_WIDTH - 18] + "..."
                    diagram.append(f"{a_str:<{LINE_WIDTH - 14}} {badge:>13}")

            if desc_uri:
                desc_passed = False
                if prof_node:
                    desc_matches = prof_node.all_links.find_links(rel="describedby", target=desc_uri)
                    desc_passed = len(desc_matches) > 0
                badge = _status_badge(desc_passed) if prof_node else "[? UNCHECKED]"
                d_str = f"        +---> rel=\"describedby\" -> {desc_uri}"
                if len(d_str) > LINE_WIDTH - 15:
                    d_str = d_str[: LINE_WIDTH - 18] + "..."
                diagram.append(f"{d_str:<{LINE_WIDTH - 14}} {badge:>13}")

                if desc_type:
                    desc_node = nodes.get(desc_uri)
                    dt_passed = False
                    if desc_node:
                        dt_matches = desc_node.all_links.find_links(rel="type", target=desc_type)
                        dt_passed = len(dt_matches) > 0
                    badge_dt = _status_badge(dt_passed) if desc_node else "[? UNCHECKED]"
                    pipe_prefix = "        |     +--- " if type_uri else "              +--- "
                    dt_str = f"{pipe_prefix}rel=\"type\"        -> {desc_type}"
                    if len(dt_str) > LINE_WIDTH - 15:
                        dt_str = dt_str[: LINE_WIDTH - 18] + "..."
                    diagram.append(f"{dt_str:<{LINE_WIDTH - 14}} {badge_dt:>13}")

            if type_uri:
                type_passed = False
                if prof_node:
                    type_matches = prof_node.all_links.find_links(rel="type", target=type_uri)
                    type_passed = len(type_matches) > 0
                badge = _status_badge(type_passed) if prof_node else "[? UNCHECKED]"
                t_str = f"        +---> rel=\"type\"        -> {type_uri}"
                if len(t_str) > LINE_WIDTH - 15:
                    t_str = t_str[: LINE_WIDTH - 18] + "..."
                diagram.append(f"{t_str:<{LINE_WIDTH - 14}} {badge:>13}")

        return "\n".join(diagram)

    @staticmethod
    def _render_pt02(roles: Dict[str, Any], result: Any, nodes: Dict[str, ResourceNode]) -> str:
        res_uri = roles.get("resource") or getattr(result, "target_url", "Resource")
        comp_uri = roles.get("composite_profile") or "Composite Profile"
        members = roles.get("member_profiles", [])
        if isinstance(members, str):
            members = [members]

        target_url = getattr(result, "target_url", "")
        res_node = nodes.get(res_uri) or (getattr(result, "harvest_node", None) if target_url == res_uri else None)
        comp_passed = False
        if res_node:
            comp_matches = res_node.all_links.find_links(rel="profile", target=comp_uri if comp_uri != "Composite Profile" else None)
            comp_passed = len(comp_matches) > 0
        elif target_url == comp_uri:
            comp_passed = True
        else:
            comp_passed = getattr(result, "passed", False)

        comp_node = nodes.get(comp_uri) or (getattr(result, "harvest_node", None) if target_url == comp_uri else None)

        diagram = []
        diagram.extend(_make_box("Resource", res_uri))
        diagram.extend(_make_down_arrow('rel="profile"', _status_badge(comp_passed)))
        diagram.extend(_make_box("Composite Profile", comp_uri))
        diagram.append("        |")
        diagram.append('        | Member Profiles (rel="http://schema.org/hasPart"):')

        for m in members:
            m_uri = m if isinstance(m, str) else m.get("uri", str(m))
            m_passed = False
            if comp_node:
                m_matches = comp_node.all_links.find_links(rel="http://schema.org/hasPart", target=m_uri)
                if not m_matches:
                    m_matches = comp_node.all_links.find_links(target=m_uri)
                m_passed = len(m_matches) > 0
            elif target_url == comp_uri:
                m_passed = getattr(result, "passed", False)
            m_str = f"        +---> {m_uri}"
            if len(m_str) > LINE_WIDTH - 12:
                m_str = m_str[: LINE_WIDTH - 15] + "..."
            diagram.append(f"{m_str:<{LINE_WIDTH - 12}} {_status_badge(m_passed)}")

        return "\n".join(diagram)

    @staticmethod
    def _render_pt03(roles: Dict[str, Any], result: Any, nodes: Dict[str, ResourceNode]) -> str:
        concept_uri = roles.get("concept") or roles.get("self") or getattr(result, "target_url", "Concept")
        menu_uri = roles.get("variant_menu")
        variants = roles.get("variants", [])
        if isinstance(variants, str):
            variants = [{"uri": variants}]

        c_node = nodes.get(concept_uri)

        diagram = []
        diagram.extend(_make_box("Concept Identity", concept_uri))
        diagram.append("        |")

        if menu_uri:
            menu_passed = False
            if c_node:
                m_matches = c_node.all_links.find_links(rel="linkset", target=menu_uri)
                menu_passed = len(m_matches) > 0
            m_str = f"        +--- rel=\"linkset\" -> {menu_uri}"
            if len(m_str) > LINE_WIDTH - 12:
                m_str = m_str[: LINE_WIDTH - 15] + "..."
            diagram.append(f"{m_str:<{LINE_WIDTH - 12}} {_status_badge(menu_passed)}")

        diagram.append('        | Representation Variants (rel="alternate"):')
        for v in variants:
            v_uri = v.get("uri") if isinstance(v, dict) else str(v)
            v_type = v.get("type", "") if isinstance(v, dict) else ""
            v_passed = False
            if c_node:
                v_matches = c_node.all_links.find_links(rel="alternate", target=v_uri)
                v_passed = len(v_matches) > 0

            v_node = nodes.get(v_uri)
            self_passed = False
            if v_node:
                s_matches = v_node.all_links.find_links(rel="self", target=concept_uri)
                self_passed = len(s_matches) > 0

            type_info = f" [{v_type}]" if v_type else ""
            v_str = f"        +---> {v_uri}{type_info}"
            if len(v_str) > LINE_WIDTH - 25:
                v_str = v_str[: LINE_WIDTH - 28] + "..."
            diagram.append(f"{v_str} {_status_badge(v_passed)} -> self {_status_badge(self_passed)}")

        return "\n".join(diagram)

    @staticmethod
    def _render_pt04(roles: Dict[str, Any], result: Any, nodes: Dict[str, ResourceNode]) -> str:
        pid_uri = roles.get("pid") or "PID URI"
        content_uri = roles.get("content") or getattr(result, "target_url", "Content URI")
        descriptions = roles.get("descriptions", [])
        if isinstance(descriptions, str):
            descriptions = [{"uri": descriptions}]

        target_url = getattr(result, "target_url", "")
        res_uri = roles.get("resource") or roles.get("dataset") or roles.get("concept") or content_uri

        c_node = nodes.get(content_uri) or (getattr(result, "harvest_node", None) if target_url == content_uri else None)
        cite_passed = False
        if c_node:
            cite_matches = c_node.all_links.find_links(rel="cite-as", target=pid_uri if pid_uri != "PID URI" else None)
            cite_passed = len(cite_matches) > 0
        else:
            cite_passed = getattr(result, "passed", False)

        diagram = []
        diagram.extend(_make_box("Content Payload", content_uri))
        diagram.extend([
            "        |                                    |",
            f"        | rel=\"cite-as\" {_status_badge(cite_passed)}             | rel=\"describedby\"",
            "        v                                    v",
            "  [ PID / Handle ]                 [ Metadata Descriptions ]",
            f"  {pid_uri[:60]}",
        ])

        for d in descriptions:
            d_uri = d.get("uri") if isinstance(d, dict) else str(d)
            d_type = d.get("type", "") if isinstance(d, dict) else ""
            d_passed = False
            if c_node:
                d_matches = c_node.all_links.find_links(rel="describedby", target=d_uri)
                d_passed = len(d_matches) > 0

            d_node = nodes.get(d_uri) or (getattr(result, "harvest_node", None) if target_url == d_uri else None)
            describes_passed = False
            if d_node:
                desc_matches = d_node.all_links.find_links(rel="describes", target=res_uri) or d_node.all_links.find_links(rel="describes", target=content_uri)
                describes_passed = len(desc_matches) > 0
            elif target_url == d_uri:
                describes_passed = getattr(result, "passed", False)

            type_info = f" ({d_type})" if d_type else ""
            d_str = f"  * {d_uri}{type_info}"
            if len(d_str) > LINE_WIDTH - 40:
                d_str = d_str[: LINE_WIDTH - 43] + "..."
            diagram.append(f"{d_str} {_status_badge(d_passed)} (describes resource {_status_badge(describes_passed)})")

        return "\n".join(diagram)

    @staticmethod
    def _render_pt05(roles: Dict[str, Any], result: Any, nodes: Dict[str, ResourceNode]) -> str:
        ds_uri = roles.get("dataset") or "Dataset URI"
        base_api = roles.get("base_api") or getattr(result, "target_url", "Base API")
        frag_api = roles.get("fragment_api")
        serv_desc = roles.get("service_desc")
        api_cat = roles.get("api_catalog")

        b_node = nodes.get(base_api)
        cite_passed = False
        if b_node:
            cite_matches = b_node.all_links.find_links(rel="cite-as", target=ds_uri)
            cite_passed = len(cite_matches) > 0

        diagram = []
        diagram.extend(_make_box("Dataset", ds_uri))
        diagram.extend([
            "        ^",
            f"        | rel=\"cite-as\" {_status_badge(cite_passed)}",
            "        |",
        ])
        diagram.extend(_make_box("Base API Service", base_api))

        if frag_api:
            f_passed = False
            f_coll_passed = False
            if b_node:
                f_matches = b_node.all_links.find_links(rel="item", target=frag_api)
                f_passed = len(f_matches) > 0
            f_node = nodes.get(frag_api)
            if f_node:
                c_matches = f_node.all_links.find_links(rel="collection", target=base_api)
                f_coll_passed = len(c_matches) > 0
            f_str = f"        +---> Fragment API: {frag_api}"
            if len(f_str) > LINE_WIDTH - 28:
                f_str = f_str[: LINE_WIDTH - 31] + "..."
            diagram.append(f"{f_str} {_status_badge(f_passed)} (collection {_status_badge(f_coll_passed)})")

        if serv_desc:
            sd_passed = False
            if b_node:
                sd_matches = b_node.all_links.find_links(rel="service-desc", target=serv_desc)
                sd_passed = len(sd_matches) > 0
            sd_str = f"        +---> Service Desc (OpenAPI): {serv_desc}"
            if len(sd_str) > LINE_WIDTH - 12:
                sd_str = sd_str[: LINE_WIDTH - 15] + "..."
            diagram.append(f"{sd_str:<{LINE_WIDTH - 12}} {_status_badge(sd_passed)}")

        if api_cat:
            cat_passed = False
            if b_node:
                cat_matches = b_node.all_links.find_links(rel="api-catalog", target=api_cat)
                cat_passed = len(cat_matches) > 0
            cat_str = f"        +---> API Catalog: {api_cat}"
            if len(cat_str) > LINE_WIDTH - 12:
                cat_str = cat_str[: LINE_WIDTH - 15] + "..."
            diagram.append(f"{cat_str:<{LINE_WIDTH - 12}} {_status_badge(cat_passed)}")

        return "\n".join(diagram)

    @staticmethod
    def _render_pt06(roles: Dict[str, Any], result: Any, nodes: Dict[str, ResourceNode]) -> str:
        def _clean_list(v: Any) -> List[str]:
            if v is None:
                return []
            if isinstance(v, list):
                res = []
                for it in v:
                    if isinstance(it, str) and it.strip():
                        res.append(it.strip())
                    elif isinstance(it, dict):
                        u = it.get("uri") or it.get("href") or it.get("url")
                        if u and str(u).strip():
                            res.append(str(u).strip())
                return res
            if isinstance(v, dict):
                u = v.get("uri") or v.get("href") or v.get("url")
                return [str(u).strip()] if u and str(u).strip() else []
            if isinstance(v, str) and v.strip():
                return [v.strip()]
            return []

        host_uri = roles.get("host") or "Host"
        sitemap_uri = roles.get("sitemap")
        resources = roles.get("resources", [])

        case_name = getattr(result, "case_name", "") or ""
        target_url = getattr(result, "target_url", "") or ""
        exp = getattr(result, "expectation", None)
        exp_anchor = getattr(exp, "anchor", None) if exp else None
        exp_rel = getattr(exp, "rel", None) if exp else None

        # Parse indented resource specs
        parsed_specs: List[Dict[str, Any]] = []
        for r in resources:
            if isinstance(r, dict):
                r_uri = (r.get("uri") or r.get("href") or r.get("url") or r.get("loc") or "").strip()
                if r_uri:
                    parsed_specs.append({
                        "uri": r_uri,
                        "linksets": _clean_list(r.get("linkset") or r.get("linksets")),
                        "alternates": _clean_list(r.get("alternate") or r.get("alternates")),
                        "profiles": _clean_list(r.get("profile") or r.get("profiles")),
                    })

        # Check if this assertion corresponds to an alternate or resource consistency test
        is_consistency_case = (
            "Alternate Consistency" in case_name
            or "Discovery & Links" in case_name
            or (exp_rel in ("alternate", "linkset", "profile") and bool(exp_anchor))
        )

        if is_consistency_case and parsed_specs:
            relevant_spec = None
            for spec in parsed_specs:
                r_uri = spec["uri"]
                if exp_anchor and exp_anchor == r_uri:
                    relevant_spec = spec
                    break
                if target_url == r_uri or target_url in spec["linksets"]:
                    relevant_spec = spec
                    break
                if f"[{r_uri}]" in case_name or any(f"[{ls}]" in case_name for ls in spec["linksets"]):
                    relevant_spec = spec
                    break

            if relevant_spec and (relevant_spec["linksets"] or relevant_spec["alternates"] or relevant_spec["profiles"]):
                return ASCIIDiagramRenderer._render_pt06_alternate_consistency(
                    res_spec=relevant_spec,
                    roles=roles,
                    result=result,
                    nodes=nodes,
                )

        robots_raw = roles.get("robots_txt")
        if robots_raw is None:
            robots_raw = True

        robots_enabled = True
        robots_uri = f"{host_uri}/robots.txt"

        if isinstance(robots_raw, bool):
            robots_enabled = robots_raw
        elif isinstance(robots_raw, str):
            val_lower = robots_raw.strip().lower()
            if val_lower in ("false", "no", "0"):
                robots_enabled = False
            elif val_lower not in ("true", "yes", "1"):
                robots_uri = robots_raw.strip()

        diagram = []
        diagram.extend(_make_box("Host", host_uri))

        if robots_enabled:
            r_node = nodes.get(robots_uri)
            sm_passed = False
            if r_node and sitemap_uri:
                sm_matches = r_node.all_links.find_links(target=sitemap_uri)
                sm_passed = len(sm_matches) > 0

            diagram.extend([
                "        |",
                "        v",
                f"  [ robots.txt: {robots_uri} ]" if len(robots_uri) <= LINE_WIDTH - 18 else f"  [ robots.txt: {robots_uri[: LINE_WIDTH - 21]}... ]",
                f"        | Sitemap directive {_status_badge(sm_passed)}",
                "        v",
                f"  [ sitemap.xml: {str(sitemap_uri)} ]" if len(str(sitemap_uri)) <= LINE_WIDTH - 19 else f"  [ sitemap.xml: {str(sitemap_uri)[: LINE_WIDTH - 22]}... ]",
            ])
        else:
            diagram.extend([
                "        |",
                "        v (direct sitemap)",
                f"  [ sitemap.xml: {str(sitemap_uri)} ]" if len(str(sitemap_uri)) <= LINE_WIDTH - 19 else f"  [ sitemap.xml: {str(sitemap_uri)[: LINE_WIDTH - 22]}... ]",
            ])

        if resources:
            diagram.append("        | Resource links:")
            sm_node = nodes.get(sitemap_uri)

            def _clean_list(v: Any) -> List[str]:
                if v is None:
                    return []
                if isinstance(v, list):
                    res = []
                    for it in v:
                        if isinstance(it, str) and it.strip():
                            res.append(it.strip())
                        elif isinstance(it, dict):
                            u = it.get("uri") or it.get("href") or it.get("url")
                            if u and str(u).strip():
                                res.append(str(u).strip())
                    return res
                if isinstance(v, dict):
                    u = v.get("uri") or v.get("href") or v.get("url")
                    return [str(u).strip()] if u and str(u).strip() else []
                if isinstance(v, str) and v.strip():
                    return [v.strip()]
                return []

            for res in resources:
                if isinstance(res, str):
                    res_uri = res.strip()
                    r_linksets: List[str] = []
                    r_alts: List[str] = []
                    r_profs: List[str] = []
                elif isinstance(res, dict):
                    res_uri = (res.get("uri") or res.get("href") or res.get("url") or res.get("loc") or str(res)).strip()
                    r_linksets = _clean_list(res.get("linkset") or res.get("linksets"))
                    r_alts = _clean_list(res.get("alternate") or res.get("alternates"))
                    r_profs = _clean_list(res.get("profile") or res.get("profiles"))
                else:
                    res_uri = str(res)
                    r_linksets = []
                    r_alts = []
                    r_profs = []

                res_passed = False
                if sm_node:
                    res_matches = sm_node.all_links.find_links(target=res_uri)
                    res_passed = len(res_matches) > 0
                res_str = f"        +---> {res_uri}"
                if len(res_str) > LINE_WIDTH - 15:
                    res_str = res_str[: LINE_WIDTH - 18] + "..."
                diagram.append(f"{res_str:<{LINE_WIDTH - 14}} {_status_badge(res_passed):>13}")

                r_node = nodes.get(res_uri)
                sub_prefix = "        |     +--- "

                for ls in r_linksets:
                    ls_passed = False
                    if sm_node and sm_node.all_links.find_links(rel="linkset", anchor=res_uri, target=ls):
                        ls_passed = True
                    elif r_node and r_node.all_links.find_links(rel="linkset", target=ls):
                        ls_passed = True
                    ls_str = f"{sub_prefix}linkset: {ls}"
                    if len(ls_str) > LINE_WIDTH - 15:
                        ls_str = ls_str[: LINE_WIDTH - 18] + "..."
                    diagram.append(f"{ls_str:<{LINE_WIDTH - 14}} {_status_badge(ls_passed):>13}")

                for alt in r_alts:
                    alt_passed = False
                    if sm_node and sm_node.all_links.find_links(rel="alternate", anchor=res_uri, target=alt):
                        alt_passed = True
                    elif r_node and r_node.all_links.find_links(rel="alternate", target=alt):
                        alt_passed = True
                    else:
                        for ls in r_linksets:
                            ls_node = nodes.get(ls)
                            if ls_node and ls_node.all_links.find_links(rel="alternate", anchor=res_uri, target=alt):
                                alt_passed = True
                                break
                    alt_str = f"{sub_prefix}alternate: {alt}"
                    if len(alt_str) > LINE_WIDTH - 15:
                        alt_str = alt_str[: LINE_WIDTH - 18] + "..."
                    diagram.append(f"{alt_str:<{LINE_WIDTH - 14}} {_status_badge(alt_passed):>13}")

                for prof in r_profs:
                    prof_passed = False
                    if sm_node and sm_node.all_links.find_links(rel="profile", anchor=res_uri, target=prof):
                        prof_passed = True
                    elif r_node and r_node.all_links.find_links(rel="profile", target=prof):
                        prof_passed = True
                    prof_str = f"{sub_prefix}profile: {prof}"
                    if len(prof_str) > LINE_WIDTH - 15:
                        prof_str = prof_str[: LINE_WIDTH - 18] + "..."
                    diagram.append(f"{prof_str:<{LINE_WIDTH - 14}} {_status_badge(prof_passed):>13}")

        return "\n".join(diagram)

    @staticmethod
    def _render_pt06_alternate_consistency(
        res_spec: Dict[str, Any],
        roles: Dict[str, Any],
        result: Any,
        nodes: Dict[str, ResourceNode],
    ) -> str:
        res_uri = res_spec["uri"]
        sitemap_uri = roles.get("sitemap") or ""
        r_linksets = res_spec.get("linksets", [])
        r_alts = res_spec.get("alternates", [])
        r_profs = res_spec.get("profiles", [])
        primary_ls = r_linksets[0] if r_linksets else None

        sm_node = nodes.get(sitemap_uri)
        res_node = nodes.get(res_uri)
        ls_node = nodes.get(primary_ls) if primary_ls else None

        diagram: List[str] = []
        diagram.extend(_make_box("Alternate Resources & Consistency Analysis", res_uri))
        diagram.append(f"  Target Resource:   {res_uri}")
        if primary_ls:
            diagram.append(f"  Linkset Document:  {primary_ls}")
        if sitemap_uri:
            diagram.append(f"  Sitemap XML:       {sitemap_uri}")
        diagram.append("")

        # Perspective 1: Sitemap
        diagram.append(f"[1] Sitemap Perspective ({sitemap_uri or 'sitemap.xml'}):")
        sm_has_loc = False
        if sm_node:
            sm_has_loc = len(sm_node.all_links.find_links(target=res_uri)) > 0
        loc_str = f"      +--- <loc> entry: {res_uri}"
        if len(loc_str) > LINE_WIDTH - 15:
            loc_str = loc_str[: LINE_WIDTH - 18] + "..."
        diagram.append(f"{loc_str:<{LINE_WIDTH - 14}} {_status_badge(sm_has_loc, 'NOT FOUND'):>13}")

        for ls in r_linksets:
            found_ls = False
            if sm_node:
                found_ls = len(sm_node.all_links.find_links(rel="linkset", anchor=res_uri, target=ls)) > 0
            ls_str = f"      +--- rel=\"linkset\"   -> {ls}"
            if len(ls_str) > LINE_WIDTH - 15:
                ls_str = ls_str[: LINE_WIDTH - 18] + "..."
            diagram.append(f"{ls_str:<{LINE_WIDTH - 14}} {_status_badge(found_ls, 'NOT FOUND'):>13}")

        for alt in r_alts:
            found_alt = False
            if sm_node:
                found_alt = len(sm_node.all_links.find_links(rel="alternate", anchor=res_uri, target=alt)) > 0
            alt_str = f"      +--- rel=\"alternate\" -> {alt}"
            if len(alt_str) > LINE_WIDTH - 15:
                alt_str = alt_str[: LINE_WIDTH - 18] + "..."
            diagram.append(f"{alt_str:<{LINE_WIDTH - 14}} {_status_badge(found_alt, 'NOT FOUND'):>13}")

        for prof in r_profs:
            found_prof = False
            if sm_node:
                found_prof = len(sm_node.all_links.find_links(rel="profile", anchor=res_uri, target=prof)) > 0
            prof_str = f"      +--- rel=\"profile\"   -> {prof}"
            if len(prof_str) > LINE_WIDTH - 15:
                prof_str = prof_str[: LINE_WIDTH - 18] + "..."
            diagram.append(f"{prof_str:<{LINE_WIDTH - 14}} {_status_badge(found_prof, 'NOT FOUND'):>13}")

        diagram.append("")

        # Perspective 2: Resource Headers
        diagram.append(f"[2] Resource Headers Perspective (GET {res_uri}):")
        res_avail = (res_node is not None and res_node.status_code == 200)
        res_status_str = f"      +--- HTTP Status 200: {res_uri}"
        if len(res_status_str) > LINE_WIDTH - 15:
            res_status_str = res_status_str[: LINE_WIDTH - 18] + "..."
        diagram.append(f"{res_status_str:<{LINE_WIDTH - 14}} {_status_badge(res_avail, 'FAILED'):>13}")

        for ls in r_linksets:
            found_ls = False
            if res_node:
                found_ls = len(res_node.all_links.find_links(rel="linkset", target=ls)) > 0
            ls_str = f"      +--- rel=\"linkset\"   -> {ls}"
            if len(ls_str) > LINE_WIDTH - 15:
                ls_str = ls_str[: LINE_WIDTH - 18] + "..."
            diagram.append(f"{ls_str:<{LINE_WIDTH - 14}} {_status_badge(found_ls, 'NOT FOUND'):>13}")

        for alt in r_alts:
            found_alt = False
            if res_node:
                found_alt = len(res_node.all_links.find_links(rel="alternate", target=alt)) > 0
            alt_str = f"      +--- rel=\"alternate\" -> {alt}"
            if len(alt_str) > LINE_WIDTH - 15:
                alt_str = alt_str[: LINE_WIDTH - 18] + "..."
            diagram.append(f"{alt_str:<{LINE_WIDTH - 14}} {_status_badge(found_alt, 'NOT FOUND'):>13}")

        for prof in r_profs:
            found_prof = False
            if res_node:
                found_prof = len(res_node.all_links.find_links(rel="profile", target=prof)) > 0
            prof_str = f"      +--- rel=\"profile\"   -> {prof}"
            if len(prof_str) > LINE_WIDTH - 15:
                prof_str = prof_str[: LINE_WIDTH - 18] + "..."
            diagram.append(f"{prof_str:<{LINE_WIDTH - 14}} {_status_badge(found_prof, 'NOT FOUND'):>13}")

        diagram.append("")

        # Perspective 3: Linkset Document
        if primary_ls:
            diagram.append(f"[3] Linkset Perspective (GET {primary_ls} with anchor={res_uri}):")
            ls_avail = (ls_node is not None and ls_node.status_code == 200)
            ls_status_str = f"      +--- HTTP Status 200: {primary_ls}"
            if len(ls_status_str) > LINE_WIDTH - 15:
                ls_status_str = ls_status_str[: LINE_WIDTH - 18] + "..."
            diagram.append(f"{ls_status_str:<{LINE_WIDTH - 14}} {_status_badge(ls_avail, 'FAILED'):>13}")

            for alt in r_alts:
                found_alt = False
                if ls_node:
                    found_alt = len(ls_node.all_links.find_links(rel="alternate", anchor=res_uri, target=alt)) > 0
                alt_str = f"      +--- rel=\"alternate\" -> {alt}"
                if len(alt_str) > LINE_WIDTH - 15:
                    alt_str = alt_str[: LINE_WIDTH - 18] + "..."
                diagram.append(f"{alt_str:<{LINE_WIDTH - 14}} {_status_badge(found_alt, 'NOT FOUND'):>13}")

            for prof in r_profs:
                found_prof = False
                if ls_node:
                    found_prof = len(ls_node.all_links.find_links(rel="profile", anchor=res_uri, target=prof)) > 0
                prof_str = f"      +--- rel=\"profile\"   -> {prof}"
                if len(prof_str) > LINE_WIDTH - 15:
                    prof_str = prof_str[: LINE_WIDTH - 18] + "..."
                diagram.append(f"{prof_str:<{LINE_WIDTH - 14}} {_status_badge(found_prof, 'NOT FOUND'):>13}")

            diagram.append("")
        else:
            diagram.append("[3] Linkset Perspective: (No linkset configured for this resource)")
            diagram.append("")

        # Consistency Cross-Reference Matrix
        diagram.append("-" * LINE_WIDTH)
        diagram.append("Consistency Triangulation Matrix:")

        col1_w = max(40, LINE_WIDTH - 60)
        hdr = f"{'Target Relation / URI':<{col1_w}} | {'Sitemap':^12} | {'Resource':^12} | {'Linkset':^12} | {'Consistency':^15}"
        diagram.append(hdr)
        diagram.append("-" * min(len(hdr), LINE_WIDTH))

        matrix_items = []
        for ls in r_linksets:
            matrix_items.append(("linkset", ls))
        for alt in r_alts:
            matrix_items.append(("alternate", alt))
        for prof in r_profs:
            matrix_items.append(("profile", prof))

        for rel, target_uri in matrix_items:
            in_sm = False
            if sm_node:
                in_sm = len(sm_node.all_links.find_links(rel=rel, anchor=res_uri, target=target_uri)) > 0
            sm_str = "[✓ PASS]" if in_sm else "[✗ MISSING]"

            in_res = False
            if res_node:
                in_res = len(res_node.all_links.find_links(rel=rel, target=target_uri)) > 0
            res_str = "[✓ PASS]" if in_res else "[✗ MISSING]"

            if primary_ls:
                in_ls = False
                if ls_node:
                    in_ls = len(ls_node.all_links.find_links(rel=rel, anchor=res_uri, target=target_uri)) > 0
                ls_str = "[✓ PASS]" if in_ls else "[✗ MISSING]"
                if rel == "linkset":
                    all_match = (in_sm and in_res)
                    ls_str = "    N/A     "
                else:
                    all_match = (in_sm and in_res and in_ls)
            else:
                ls_str = "    N/A     "
                all_match = (in_sm and in_res)

            sync_str = "[✓ IN SYNC]" if all_match else "[✗ DESYNC]"

            display_target = f"{rel:<9} -> {target_uri}"
            if len(display_target) > col1_w:
                display_target = display_target[: col1_w - 3] + "..."

            diagram.append(f"{display_target:<{col1_w}} | {sm_str:^12} | {res_str:^12} | {ls_str:^12} | {sync_str:^15}")

        return "\n".join(diagram)

    @staticmethod
    def _render_pt07(roles: Dict[str, Any], result: Any, nodes: Dict[str, ResourceNode]) -> str:
        cat_uri = roles.get("api_catalog") or getattr(result, "target_url", "API Catalog")
        sm_index_uri = roles.get("sitemap_index") or roles.get("sitemap")
        host_uri = roles.get("host")
        if not host_uri:
            ref = cat_uri or sm_index_uri
            if ref:
                parsed = urlparse(ref)
                if parsed.scheme and parsed.netloc:
                    host_uri = f"{parsed.scheme}://{parsed.netloc}"

        robots_raw = roles.get("robots_txt")
        if robots_raw is None:
            robots_raw = roles.get("robots")
        robots_url: Optional[str] = None
        if robots_raw is None or robots_raw is True:
            if host_uri:
                robots_url = f"{host_uri.rstrip('/')}/robots.txt"
        elif isinstance(robots_raw, str):
            vl = robots_raw.strip().lower()
            if vl == "true":
                if host_uri:
                    robots_url = f"{host_uri.rstrip('/')}/robots.txt"
            elif vl != "false":
                robots_url = robots_raw.strip()

        cat_sm_uri = roles.get("api_catalog_sitemap")
        if not cat_sm_uri and host_uri:
            cat_sm_uri = f"{host_uri.rstrip('/')}/.well-known/api-catalog/sitemap-index.xml"

        raw_endpoints = roles.get("api_endpoints") or roles.get("endpoints") or []
        if isinstance(raw_endpoints, str):
            raw_endpoints = [raw_endpoints]

        endpoints_data: List[Dict[str, Any]] = []
        for ep in raw_endpoints:
            if isinstance(ep, str):
                ep_u = ep.strip()
                if ep_u:
                    endpoints_data.append({
                        "uri": ep_u,
                        "sitemap": f"{ep_u.rstrip('/')}/sitemap.xml",
                        "profile": None,
                        "subresources": [],
                    })
            elif isinstance(ep, dict):
                ep_u = (ep.get("uri") or ep.get("href") or ep.get("target") or "").strip()
                if not ep_u:
                    continue
                sub_sm = ep.get("sitemap") or ep.get("sub_sitemap")
                if not sub_sm:
                    sub_sm = f"{ep_u.rstrip('/')}/sitemap.xml"
                raw_subs = ep.get("subresources") or ep.get("resources") or []
                if isinstance(raw_subs, str):
                    raw_subs = [raw_subs]
                subs = [r if isinstance(r, str) else r.get("uri", r.get("href")) for r in raw_subs if r]
                endpoints_data.append({
                    "uri": ep_u,
                    "sitemap": sub_sm,
                    "profile": ep.get("profile"),
                    "subresources": subs,
                })

        # Backward compatibility for top-level resources
        top_res = roles.get("resources") or []
        if isinstance(top_res, str):
            top_res = [top_res]
        if top_res and endpoints_data and not endpoints_data[0]["subresources"]:
            for r in top_res:
                r_u = r if isinstance(r, str) else r.get("uri", r.get("href"))
                if r_u:
                    endpoints_data[0]["subresources"].append(r_u)

        diagram = []

        # ---------------------------------------------------------------------
        # Top: Host & robots.txt
        # ---------------------------------------------------------------------
        if host_uri:
            diagram.extend(_make_box("Host", host_uri))
        if robots_url:
            robots_node = nodes.get(robots_url)
            robots_passed = False
            if robots_node and sm_index_uri:
                r_matches = robots_node.all_links.find_links(rel="item", target=sm_index_uri)
                robots_passed = len(r_matches) > 0
            badge = _status_badge(robots_passed) if robots_node else "[? UNCHECKED]"
            diagram.append("        |")
            diagram.append(f"        v [ robots.txt: {robots_url} ]")
            if sm_index_uri:
                prompt_line = "        | Sitemap index directive"
                diagram.append(f"{prompt_line:<{LINE_WIDTH - 14}} {badge:>13}")
                diagram.append("        v")

        # ---------------------------------------------------------------------
        # Pillar 2: Sitemaps Hierarchy (sitemaps.org)
        # ---------------------------------------------------------------------
        sm_index_node = nodes.get(sm_index_uri) if sm_index_uri else None
        cat_sm_node = nodes.get(cat_sm_uri) if cat_sm_uri else None

        box2_title = "[2] Sitemaps Hierarchy (sitemaps.org)"
        box2_content = f"Root Index: {sm_index_uri}" if sm_index_uri else "Root Sitemap Index"
        diagram.extend(_make_box(box2_title, box2_content))

        diagram.append("        | Delegated Sitemaps:")

        # 2.1 Dedicated Catalog Sitemap
        if cat_sm_uri:
            in_index_passed = False
            if sm_index_node:
                matches = sm_index_node.all_links.find_links(rel="item", target=cat_sm_uri)
                in_index_passed = len(matches) > 0
            badge_index = _status_badge(in_index_passed) if sm_index_node else "[? UNCHECKED]"
            line_str = f"        +---> Catalog Sitemap: {cat_sm_uri}"
            if len(line_str) > LINE_WIDTH - 15:
                line_str = line_str[: LINE_WIDTH - 18] + "..."
            diagram.append(f"{line_str:<{LINE_WIDTH - 14}} {badge_index:>13}")

            # rel="self" back to api_catalog
            self_passed = False
            if cat_sm_node:
                s_matches = cat_sm_node.all_links.find_links(rel="self", target=cat_uri)
                self_passed = len(s_matches) > 0
            badge_self = _status_badge(self_passed) if cat_sm_node else "[? UNCHECKED]"
            s_str = f"        |     +--- rel=\"self\" -> {cat_uri}"
            if len(s_str) > LINE_WIDTH - 15:
                s_str = s_str[: LINE_WIDTH - 18] + "..."
            diagram.append(f"{s_str:<{LINE_WIDTH - 14}} {badge_self:>13}")

            # entries for each API endpoint
            for ep_spec in endpoints_data:
                ep_u = ep_spec["uri"]
                ep_in_cat_sm = False
                if cat_sm_node:
                    loc_m = cat_sm_node.all_links.find_links(rel="item", target=ep_u)
                    ep_in_cat_sm = len(loc_m) > 0
                badge_loc = _status_badge(ep_in_cat_sm) if cat_sm_node else "[? UNCHECKED]"
                loc_str = f"        |     +--- <loc> item -> {ep_u}"
                if len(loc_str) > LINE_WIDTH - 15:
                    loc_str = loc_str[: LINE_WIDTH - 18] + "..."
                diagram.append(f"{loc_str:<{LINE_WIDTH - 14}} {badge_loc:>13}")

        # 2.2 API Sub-Sitemaps
        for ep_idx, ep_spec in enumerate(endpoints_data):
            ep_u = ep_spec["uri"]
            sub_sm = ep_spec.get("sitemap")
            sub_sm_node = nodes.get(sub_sm) if sub_sm else None
            is_last_ep = (ep_idx == len(endpoints_data) - 1)
            prefix = "              " if is_last_ep else "        |     "

            if sub_sm:
                in_idx_passed = False
                if sm_index_node:
                    m = sm_index_node.all_links.find_links(rel="item", target=sub_sm)
                    in_idx_passed = len(m) > 0
                badge_in = _status_badge(in_idx_passed) if sm_index_node else "[? UNCHECKED]"
                branch = "        \\---> " if is_last_ep else "        +---> "
                sm_line = f"{branch}API Sitemap:     {sub_sm}"
                if len(sm_line) > LINE_WIDTH - 15:
                    sm_line = sm_line[: LINE_WIDTH - 18] + "..."
                diagram.append(f"{sm_line:<{LINE_WIDTH - 14}} {badge_in:>13}")

                # rel="self" back to endpoint
                self_p = False
                if sub_sm_node:
                    sm_self_m = sub_sm_node.all_links.find_links(rel="self", target=ep_u)
                    self_p = len(sm_self_m) > 0
                badge_s = _status_badge(self_p) if sub_sm_node else "[? UNCHECKED]"
                self_line = f"{prefix}+--- rel=\"self\" -> {ep_u}"
                if len(self_line) > LINE_WIDTH - 15:
                    self_line = self_line[: LINE_WIDTH - 18] + "..."
                diagram.append(f"{self_line:<{LINE_WIDTH - 14}} {badge_s:>13}")

                # subresource loc items
                for r_u in ep_spec["subresources"]:
                    r_p = False
                    if sub_sm_node:
                        rm = sub_sm_node.all_links.find_links(rel="item", target=r_u)
                        r_p = len(rm) > 0
                    badge_r = _status_badge(r_p) if sub_sm_node else "[? UNCHECKED]"
                    r_line = f"{prefix}+--- <loc> item -> {r_u}"
                    if len(r_line) > LINE_WIDTH - 15:
                        r_line = r_line[: LINE_WIDTH - 18] + "..."
                    diagram.append(f"{r_line:<{LINE_WIDTH - 14}} {badge_r:>13}")

        diagram.append("")

        # ---------------------------------------------------------------------
        # Pillar 3: API Catalog (RFC 9727 /.well-known/api-catalog)
        # ---------------------------------------------------------------------
        cat_node = nodes.get(cat_uri)
        box3_title = "[3] API Catalog (RFC 9727)"
        diagram.extend(_make_box(box3_title, cat_uri))

        if cat_sm_uri:
            alt_passed = False
            if cat_node:
                alt_m = cat_node.all_links.find_links(rel="alternate", target=cat_sm_uri)
                alt_passed = len(alt_m) > 0
            badge_alt = _status_badge(alt_passed) if cat_node else "[? UNCHECKED]"
            alt_str = f"        +---> rel=\"alternate\" -> {cat_sm_uri}"
            if len(alt_str) > LINE_WIDTH - 15:
                alt_str = alt_str[: LINE_WIDTH - 18] + "..."
            diagram.append(f"{alt_str:<{LINE_WIDTH - 14}} {badge_alt:>13}")

        for ep_spec in endpoints_data:
            ep_u = ep_spec["uri"]
            item_passed = False
            if cat_node:
                im = cat_node.all_links.find_links(rel="item", target=ep_u)
                item_passed = len(im) > 0
            badge_item = _status_badge(item_passed) if cat_node else "[? UNCHECKED]"
            it_str = f"        +---> rel=\"item\"      -> {ep_u}"
            if len(it_str) > LINE_WIDTH - 15:
                it_str = it_str[: LINE_WIDTH - 18] + "..."
            diagram.append(f"{it_str:<{LINE_WIDTH - 14}} {badge_item:>13}")

        diagram.append("")

        # ---------------------------------------------------------------------
        # Pillar 1: API Services & Subresources
        # ---------------------------------------------------------------------
        box1_title = "[1] API Services & Subresources"
        ep_summary = ", ".join(e["uri"] for e in endpoints_data) if endpoints_data else "API Endpoints"
        diagram.extend(_make_box(box1_title, ep_summary))

        for ep_spec in endpoints_data:
            ep_u = ep_spec["uri"]
            sub_sm = ep_spec.get("sitemap")
            prof = ep_spec.get("profile")
            ep_node = nodes.get(ep_u)

            ep_line = f"        +---> API Endpoint: {ep_u}"
            if len(ep_line) > LINE_WIDTH - 15:
                ep_line = ep_line[: LINE_WIDTH - 18] + "..."
            ep_reachable = ep_node is not None and getattr(ep_node, "status_code", 0) < 400
            badge_ep = _status_badge(ep_reachable) if ep_node else "[? UNCHECKED]"
            diagram.append(f"{ep_line:<{LINE_WIDTH - 14}} {badge_ep:>13}")

            # rel="api-catalog"
            cat_p = False
            if ep_node:
                cm = ep_node.all_links.find_links(rel="api-catalog", target=cat_uri)
                cat_p = len(cm) > 0
            badge_cat = _status_badge(cat_p) if ep_node else "[? UNCHECKED]"
            cat_str = f"              +--- rel=\"api-catalog\" -> {cat_uri}"
            if len(cat_str) > LINE_WIDTH - 15:
                cat_str = cat_str[: LINE_WIDTH - 18] + "..."
            diagram.append(f"{cat_str:<{LINE_WIDTH - 14}} {badge_cat:>13}")

            # rel="alternate" to sub_sitemap
            if sub_sm:
                sm_p = False
                if ep_node:
                    sm_m = ep_node.all_links.find_links(rel="alternate", target=sub_sm)
                    sm_p = len(sm_m) > 0
                badge_sm = _status_badge(sm_p) if ep_node else "[? UNCHECKED]"
                sub_str = f"              +--- rel=\"alternate\"   -> {sub_sm}"
                if len(sub_str) > LINE_WIDTH - 15:
                    sub_str = sub_str[: LINE_WIDTH - 18] + "..."
                diagram.append(f"{sub_str:<{LINE_WIDTH - 14}} {badge_sm:>13}")

            # rel="profile"
            if prof:
                pr_p = False
                if ep_node:
                    pr_m = ep_node.all_links.find_links(rel="profile", target=prof)
                    pr_p = len(pr_m) > 0
                badge_pr = _status_badge(pr_p) if ep_node else "[? UNCHECKED]"
                pr_str = f"              +--- rel=\"profile\"     -> {prof}"
                if len(pr_str) > LINE_WIDTH - 15:
                    pr_str = pr_str[: LINE_WIDTH - 18] + "..."
                diagram.append(f"{pr_str:<{LINE_WIDTH - 14}} {badge_pr:>13}")

            # Subresources collection uplink
            if ep_spec["subresources"]:
                diagram.append("              +--- Subresources (rel=\"collection\" uplink):")
                for r_u in ep_spec["subresources"]:
                    r_node = nodes.get(r_u)
                    col_p = False
                    if r_node:
                        col_m = r_node.all_links.find_links(rel="collection", target=ep_u)
                        col_p = len(col_m) > 0
                    badge_col = _status_badge(col_p) if r_node else "[? UNCHECKED]"
                    res_str = f"                   +--- {r_u}"
                    if len(res_str) > LINE_WIDTH - 15:
                        res_str = res_str[: LINE_WIDTH - 18] + "..."
                    diagram.append(f"{res_str:<{LINE_WIDTH - 14}} {badge_col:>13}")

        return "\n".join([line for line in diagram if line])

    @staticmethod
    def _render_pt08(roles: Dict[str, Any], result: Any, nodes: Dict[str, ResourceNode]) -> str:
        res_uri = roles.get("resource") or getattr(result, "target_url", "Resource")
        master_ls = roles.get("master_linkset") or "Master Linkset"
        child_ls = roles.get("child_linksets", [])

        res_node = nodes.get(res_uri)
        master_passed = False
        if res_node:
            m_matches = res_node.all_links.find_links(rel="linkset", target=master_ls if master_ls != "Master Linkset" else None)
            master_passed = len(m_matches) > 0
        else:
            master_passed = getattr(result, "passed", False)

        m_node = nodes.get(master_ls)

        diagram = []
        diagram.extend(_make_box("Resource", res_uri))
        diagram.extend(_make_down_arrow('rel="linkset"', _status_badge(master_passed)))
        diagram.extend(_make_box("Master Linkset", master_ls))
        diagram.append("        | Child Linksets:")

        for c in child_ls:
            c_uri = c if isinstance(c, str) else c.get("uri", str(c))
            c_passed = False
            if m_node:
                c_matches = m_node.all_links.find_links(target=c_uri)
                c_passed = len(c_matches) > 0
            c_str = f"        +---> {c_uri}"
            if len(c_str) > LINE_WIDTH - 12:
                c_str = c_str[: LINE_WIDTH - 15] + "..."
            diagram.append(f"{c_str:<{LINE_WIDTH - 12}} {_status_badge(c_passed)}")

        return "\n".join(diagram)

    @staticmethod
    def _render_pt09(roles: Dict[str, Any], result: Any, nodes: Dict[str, ResourceNode]) -> str:
        series_uri = roles.get("series") or getattr(result, "target_url", "Conceptual Series")
        latest_uri = roles.get("latest_version") or "Latest Version URI"
        history_uri = roles.get("version_history")
        series_pid = roles.get("series_pid")
        releases = roles.get("releases", [])

        series_node = nodes.get(series_uri)
        latest_passed = False
        history_passed = False
        pid_passed = False

        if series_node:
            l_matches = series_node.all_links.find_links(rel="latest-version", target=latest_uri if latest_uri != "Latest Version URI" else None)
            latest_passed = len(l_matches) > 0
            if history_uri:
                h_matches = series_node.all_links.find_links(rel="version-history", target=history_uri)
                history_passed = len(h_matches) > 0
            if series_pid:
                p_matches = series_node.all_links.find_links(rel="cite-as", target=series_pid)
                pid_passed = len(p_matches) > 0
        else:
            latest_passed = getattr(result, "passed", False)

        diagram = []
        diagram.extend(_make_box("Conceptual Series (Latest Identity)", series_uri))
        if series_pid:
            diagram.append(f"        | PID: {series_pid} {_status_badge(pid_passed)}")

        diagram.extend(_make_down_arrow('rel="latest-version"', _status_badge(latest_passed)))
        diagram.extend(_make_box("Latest Authoritative Release", latest_uri))

        if history_uri:
            diagram.append("        |")
            diagram.append(f"        +--- rel=\"version-history\" ---> {history_uri} {_status_badge(history_passed)}")

        if releases:
            diagram.append("        |")
            diagram.append("        | Version Succession Chain (RFC 5829):")
            for idx, r in enumerate(releases, 1):
                r_uri = r.get("uri") if isinstance(r, dict) else str(r)
                r_ver = r.get("version", f"#{idx}") if isinstance(r, dict) else f"#{idx}"
                r_pred = r.get("predecessor") if isinstance(r, dict) else None
                r_succ = r.get("successor") if isinstance(r, dict) else None
                r_pid = r.get("pid") or r.get("cite_as") if isinstance(r, dict) else None

                r_node = nodes.get(r_uri)
                pred_passed = False
                succ_passed = False
                coll_passed = False

                if r_node:
                    c_matches = r_node.all_links.find_links(rel="collection", target=series_uri)
                    coll_passed = len(c_matches) > 0
                    if r_pred:
                        p_matches = r_node.all_links.find_links(rel="predecessor-version", target=r_pred)
                        pred_passed = len(p_matches) > 0
                    if r_succ:
                        s_matches = r_node.all_links.find_links(rel="successor-version", target=r_succ)
                        succ_passed = len(s_matches) > 0

                is_latest = (r_uri == latest_uri)
                status_parts = [f"collection: {_status_badge(coll_passed)}"]
                if r_pred:
                    status_parts.append(f"pred: {_status_badge(pred_passed)}")
                if r_succ:
                    status_parts.append(f"succ: {_status_badge(succ_passed)}")

                chain_line = f"        [{'LATEST ' if is_latest else ''}v{r_ver}] {r_uri}"
                if len(chain_line) > LINE_WIDTH - 30:
                    chain_line = chain_line[: LINE_WIDTH - 33] + "..."
                diagram.append(f"{chain_line:<{LINE_WIDTH - 30}} {' '.join(status_parts)}")
                if r_pid:
                    diagram.append(f"              PID (cite-as): {r_pid}")

        return "\n".join(diagram)

    @staticmethod
    def _render_generic(result: Any, nodes: Dict[str, ResourceNode]) -> str:
        target_url = getattr(result, "target_url", "")
        passed = getattr(result, "passed", False)
        exp = getattr(result, "expectation", None)

        rel_desc = exp.description() if exp else getattr(result, "case_name", "Expectation")

        diagram = []
        diagram.extend(_make_box("Target Resource", target_url))
        diagram.extend([
            "        |",
            f"        | Assertion: {rel_desc[: LINE_WIDTH - 25]}",
            f"        | Outcome: {_status_badge(passed)}",
            "        v",
        ])

        matched = getattr(result, "matched_links", [])
        if matched:
            diagram.append(f"  Matched Links ({len(matched)}):")
            for idx, ml in enumerate(matched, 1):
                diagram.extend(_wrap_link_repr(f"    [{idx}] ", ml.display_repr(), width=LINE_WIDTH, indent="        "))
        else:
            diagram.append("  (No links matched this assertion criteria)")

        return "\n".join(diagram)
