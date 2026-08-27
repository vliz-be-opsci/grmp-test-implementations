# Linkset Usage Pattern: Detached Local Storage

## Pattern Name

[Detached local Storage][RT-P10]



## Readers caution. 

Unlike patterns RT-P01 through RT-P09, which are strictly implemented on the server-side to govern web-scale resource discovery and negotiation, RT-P10 is a client-side environment pattern. It defines a vision for how digital assets at rest on a physical filesystem maintain their machine-actionable metadata.

Instead of executing HTTP transactions, RT-P10 utilizes local file anchors (relative URIs) to bind detached local binaries to their global, web-resolvable profiles and persistent identities. It is intended for implementation by download clients, browser plugins, navigators or viewers or file-systems, and local data integration pipelines.

This should become an integral approach to proper flagging (security sandboxing) of filesystems on 'connected' devices: tracing the (untrusted) provenance of downloads should go hand in hand with caching retrieved 'navigational information' on those resources.


## Goal 

The objective of this pattern is to prevent the instant loss of semantic context, profile compliance, and web identity that occurs when a digital asset is downloaded and detached from its HTTP transport layer onto a local filesystem. By utilizing non-invasive sidecar linksets and OS-level extended attributes, downloaded files remain self-describing, discoverable, and linkable without altering the original binary payloads.


## Motivation

On the web, content negotiation and HTTP headers dynamically communicate rich metadata (such as validation profiles, licensing, and persistent identifiers). However:
* The Metadata Void: Once a file lands on a local hard drive, this transport context is stripped. Users and scripts are forced to rely entirely on ambiguous file extensions (e.g., .json, .ttl, .csv) which specify only syntax, completely hiding the specific profile or semantic namespace in use.
* The Payload Integrity Constraint: Injecting metadata directly into file binaries often corrupts them, breaks strict file-format schemas (e.g., NetCDF, Shapefiles, IFC), or violates cryptographic hashes used for data integrity.
* Legacy Software Preservation: A zero-invasive approach is required to allow legacy, profile-unaware desktop applications to read the raw files normally, while enabling modern, RT-aware agents to immediately parse the detached context.

## Encoding

The detached metadata is materialized on the filesystem using two mutually reinforcing, non-invasive mechanisms:

* The Deterministic Sidecar (*.ls.json): For any downloaded payload file named [filename].[ext], a companion file named [filename].[ext].ls.json is placed in the exact same directory. 
  * The sidecar MUST be a valid RFC 9264 Linkset serialized as JSON or JSON-LD.
  * The linkset's anchor uses a local relative file path (e.g., ./[filename].[ext]) to identify the payload.
  * The linkset binds this local anchor to global HTTP/HTTPS target URIs (for profiles, licenses, and PIDs).

* The OS-Level Accelerator (xattr): To allow rapid indexing by operating system daemons without parsing directory trees, compliant tools can optionally write an Extended File Attribute to the payload file:
  * Attribute Name: `user.linkset`
  * Attribute Value: A valid URI string pointing either to the local sidecar (file:///./[filename].[ext].ls.json) or to an authoritative live web resource.



## Sketch

``` 
Local Filesystem Directory:
+-- filename.ext                 <-- Raw downloaded payload (untouched)
+-- filename.ext.ls.json         <-- Deterministic Sidecar (JSON-LD Linkset) [3]
          | 
          +-- anchor: "./filename.ext"
          +-- rel="profile" ------> [ <profile-uri> ] 
          +-- rel="cite-as" ------> [ <doi-deref-uri> ] 
          +-- rel="license" ------> [ <license-uri> ] 
```


## Design Considerations

* The Local-to-Global Bridge: Because the sidecar is a standard [RFC 9264 linkset][RFC 9264], it seamlessly handles heterogeneous environments. A desktop validation tool can read ./aphia-record-36.json, resolve its `rel=profile` target over the internet, and validate the local file against the global schema on-the-fly.
* Disconnected (Air-Gapped) Environments: In secure or offline contexts (such as maritime research vessels at sea), the targets in the sidecar can point to a replicated local register cache (as outlined in the OGC 26-021 architecture), allowing validation to succeed completely offline.


## Implementation Example: WoRMS Aphia Record Download

In this scenario, a marine biology pipeline downloads taxonomic record 36 (the European lobster, Homarus gammarus) from the World Register of Marine Species (WoRMS) API. The pipeline downloads the bare JSON data as aphia-record-36.json, but writes a deterministic sidecar aphia-record-36.json.ls.json alongside it to preserve the Radical Transparency context.

``` 
Local Filesystem Directory:
+-- aphia-record-36.json         <-- Raw downloaded payload (untouched)
+-- aphia-record-36.json.ls.json <-- Deterministic Sidecar (JSON-LD Linkset)
```

Deterministic Sidecar (aphia-record-36.json.ls.json):
```json
{
  "linkset": [
    {
      "anchor": "./aphia-record-36.json",
      "profile": [{ "href": "https://marinespecies.org/ns/profiles/aphia-record+json" }],
      "cite-as": [{ "href": "https://doi.org/10.14284/170" }],
      "license": [{ "href": "https://creativecommons.org/licenses/by/4.0/" }],
      "alternate": [
        { 
          "href": "https://marinespecies.org/id/taxname/36",
          "type": "text/turtle"
        }
      ]
    }
  ]
}
```

[RFC 9264]: https://www.rfc-editor.org/info/rfc9264                             "RFC 9264 Linksets"
[RT-P10]: ./10-detached-local-storage.md                                      "Detached local storage"
