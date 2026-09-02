"""
ASCII Diagram & Provenance Trace Renderer for RT Test Results.
Generates structured node-and-arrow diagrams for RT Patterns (PT-01 to PT-08)
and dynamic graphs for raw relation assertions.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
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
        desc_uri = roles.get("profile_description")
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
                    diagram.append(f"{a_str:<{LINE_WIDTH - 15}} {badge}")

            if desc_uri:
                desc_passed = False
                if prof_node:
                    desc_matches = prof_node.all_links.find_links(rel="describedby", target=desc_uri)
                    desc_passed = len(desc_matches) > 0
                badge = _status_badge(desc_passed) if prof_node else "[? UNCHECKED]"
                d_str = f"        +---> rel=\"describedby\" -> {desc_uri}"
                if len(d_str) > LINE_WIDTH - 15:
                    d_str = d_str[: LINE_WIDTH - 18] + "..."
                diagram.append(f"{d_str:<{LINE_WIDTH - 15}} {badge}")

            if type_uri:
                type_passed = False
                if prof_node:
                    type_matches = prof_node.all_links.find_links(rel="type", target=type_uri)
                    type_passed = len(type_matches) > 0
                badge = _status_badge(type_passed) if prof_node else "[? UNCHECKED]"
                t_str = f"        +---> rel=\"type\"        -> {type_uri}"
                if len(t_str) > LINE_WIDTH - 15:
                    t_str = t_str[: LINE_WIDTH - 18] + "..."
                diagram.append(f"{t_str:<{LINE_WIDTH - 15}} {badge}")

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
        host_uri = roles.get("host") or "Host"
        robots_uri = roles.get("robots_txt") or f"{host_uri}/robots.txt"
        sitemap_uri = roles.get("sitemap")
        resources = roles.get("resources", [])

        r_node = nodes.get(robots_uri)
        sm_passed = False
        if r_node and sitemap_uri:
            sm_matches = r_node.all_links.find_links(target=sitemap_uri)
            sm_passed = len(sm_matches) > 0

        diagram = []
        diagram.extend(_make_box("Host", host_uri))
        diagram.extend([
            "        |",
            "        v",
            f"  [ robots.txt: {robots_uri} ]" if len(robots_uri) <= LINE_WIDTH - 18 else f"  [ robots.txt: {robots_uri[: LINE_WIDTH - 21]}... ]",
            f"        | Sitemap directive {_status_badge(sm_passed)}",
            "        v",
            f"  [ sitemap.xml: {str(sitemap_uri)} ]" if len(str(sitemap_uri)) <= LINE_WIDTH - 19 else f"  [ sitemap.xml: {str(sitemap_uri)[: LINE_WIDTH - 22]}... ]",
        ])

        if resources:
            diagram.append("        | Resource links:")
            sm_node = nodes.get(sitemap_uri)
            for res in resources:
                res_uri = res if isinstance(res, str) else res.get("uri", str(res))
                res_passed = False
                if sm_node:
                    res_matches = sm_node.all_links.find_links(target=res_uri)
                    res_passed = len(res_matches) > 0
                res_str = f"        +---> {res_uri}"
                if len(res_str) > LINE_WIDTH - 12:
                    res_str = res_str[: LINE_WIDTH - 15] + "..."
                diagram.append(f"{res_str:<{LINE_WIDTH - 12}} {_status_badge(res_passed)}")

        return "\n".join(diagram)

    @staticmethod
    def _render_pt07(roles: Dict[str, Any], result: Any, nodes: Dict[str, ResourceNode]) -> str:
        cat_uri = roles.get("api_catalog") or getattr(result, "target_url", "API Catalog")
        sm_uri = roles.get("api_catalog_sitemap")
        endpoints = roles.get("api_endpoints", [])

        cat_node = nodes.get(cat_uri)
        sm_passed = False
        if cat_node and sm_uri:
            sm_matches = cat_node.all_links.find_links(target=sm_uri)
            sm_passed = len(sm_matches) > 0

        diagram = []
        diagram.extend(_make_box("API Catalog", cat_uri))
        if sm_uri:
            diagram.append(f"        | Sitemap link {_status_badge(sm_passed)}")
            sm_str = f"        v [ {sm_uri} ]"
            if len(sm_str) > LINE_WIDTH:
                sm_str = sm_str[: LINE_WIDTH - 5] + "... ]"
            diagram.append(sm_str)

        if endpoints:
            diagram.append("        | Feed Endpoints:")
            sm_node = nodes.get(sm_uri) or cat_node
            for ep in endpoints:
                ep_uri = ep.get("uri") if isinstance(ep, dict) else str(ep)
                ep_prof = ep.get("profile") if isinstance(ep, dict) else None
                ep_sub_sm = ep.get("sub_sitemap") if isinstance(ep, dict) else None
                ep_passed = False
                if sm_node:
                    ep_matches = sm_node.all_links.find_links(target=ep_uri)
                    ep_passed = len(ep_matches) > 0
                prof_str = f" ({ep_prof})" if ep_prof else ""
                ep_str = f"        +---> {ep_uri}{prof_str}"
                if len(ep_str) > LINE_WIDTH - 12:
                    ep_str = ep_str[: LINE_WIDTH - 15] + "..."
                diagram.append(f"{ep_str:<{LINE_WIDTH - 12}} {_status_badge(ep_passed)}")
                if ep_sub_sm:
                    ep_node = nodes.get(ep_uri)
                    sub_passed = False
                    if ep_node:
                        sub_matches = ep_node.all_links.find_links(rel="alternate", target=ep_sub_sm)
                        sub_passed = len(sub_matches) > 0
                    sub_str = f"              +--- sub-sitemap: {ep_sub_sm}"
                    if len(sub_str) > LINE_WIDTH - 12:
                        sub_str = sub_str[: LINE_WIDTH - 15] + "..."
                    diagram.append(f"{sub_str:<{LINE_WIDTH - 12}} {_status_badge(sub_passed)}")

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
