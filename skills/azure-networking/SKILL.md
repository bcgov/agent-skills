---
name: azure-networking
description: Azure subnet, NSG, and private-endpoint patterns for adding subnets inside an existing VNet — atomic NSG-at-creation, per-service delegation, PE subnet layout, ARM write serialization, and reference NSG layouts for PE, APIM, App Gateway, and Container Apps subnets. Tool-agnostic guidance with Terraform (azapi_resource), Bicep, and az CLI examples. Use when adding subnets, debugging delegation or PE errors, or sizing a PE subnet.
owner: bcgov
tags: [azure, networking, terraform, bicep, subnets, private-endpoints, nsg]
---

# Azure Networking — Subnets, NSGs, and Private Endpoints

## Use When
- Creating a new subnet inside an existing Azure VNet with any IaC tool (Terraform, Bicep, ARM, az CLI).
- Choosing the right service delegation for a VNet-injected workload (Container Apps, App Service / Functions VNet integration, etc.).
- Designing a private-endpoint (PE) subnet and sizing it for the services that will land on it.
- Debugging `SubnetMustNotHaveDelegation`, `SubnetDelegationCannotBeChanged`, `AnotherOperationInProgress`, `NetworkSecurityGroupNotAssociated`, or `PrivateEndpointCannotBeCreatedInSubnet`.
- Laying out NSG inbound/outbound rules for APIM, App Gateway, Container Apps Environment, or PE subnets.
- Operating under Azure Policy that requires every subnet to carry an NSG at creation time (e.g., landing-zone policies).

## Don't Use When
- Provisioning the VNet itself, or designing hub-spoke / landing-zone topology — use the upstream `azure-enterprise-infra-planner` skill.
- Authoring APIM policies, AI gateway behavior, or backend routing — use upstream `azure-aigateway`.
- Authoring App Gateway WAF custom rules or rewrite sets — out of scope.
- Provisioning AKS networking (CNI Overlay, private API server) — use upstream `azure-kubernetes`.
- General azd-style app prep that happens to need a subnet — use upstream `azure-prepare`.

*The upstream Microsoft `azure-*` skills referenced above live in the Microsoft `agent-skills` catalogue — install separately if not already in your agent environment.*

## Workflow
1. **Anchor to the BC Gov Azure Landing Zone networking rules first; these rules take precedence.** Reference: [BC Gov Azure Landing Zone — Networking](https://raw.githubusercontent.com/bcgov/public-cloud-techdocs/refs/heads/main/docs/azure/design-build-deploy/networking.md). These platform constraints **override anything below if they conflict**:
   - **Platform-protected, do not create or modify** — VNets, VNet address space, VNet DNS settings, VNet peerings, ExpressRoute / VPN / NAT / Local Gateways, **Route Tables**, and the `setbypolicy` diagnostic setting. Request changes via the [Public Cloud Service Request](https://citz-do.atlassian.net/servicedesk/customer/portal/3).
   - **IP budget** — each Project Set gets ~251 usable IPs (a single `/24`); Microsoft reserves 5 IPs per subnet; raise a Service Request for more.
   - **NSG-at-creation is mandatory** — every subnet must carry an NSG from the moment it is created, and every subnet must be a [Private Subnet](https://learn.microsoft.com/en-us/azure/virtual-network/ip-services/default-outbound-access#utilize-the-private-subnet-parameter-public-preview) (`defaultOutboundAccess = false`, Zero Trust).
   - **Egress** — all outbound traffic is forced through the central vWAN hub and firewall; teams do not add their own Internet-egress UDRs.
   - **Spoke-to-spoke is off by default** — open a Public Cloud Service Request if you need it.
   - **Prefer Private Endpoints over VNet integration / Service Endpoints** — PE DNS records are auto-registered in the centralized Private DNS Zone; teams must not create their own Private DNS Zones.
2. **Confirm the parent VNet exists** and reference it as an existing resource (Terraform `data.azurerm_virtual_network`, Bicep `resource ... existing`, az CLI `az network vnet show`) so you can pin to its ID.
3. **Pick CIDR and size** — confirm Azure's minimum subnet size for the target service, that the CIDR fits inside one of the VNet's address spaces, and that it does not overlap any existing subnet.
4. **Pick delegation** — look up the target service's required `serviceDelegations` entry (e.g., `Microsoft.App/environments` for Container Apps; `Microsoft.Web/serverFarms` for App Service / Functions VNet integration). Many services need no delegation at all (PE subnets, App Gateway, APIM internal mode).
5. **Create the subnet with its NSG attached in the same API call** — declare `networkSecurityGroup` on the subnet body itself, not as a separate association. Tool specifics: Terraform — use `azapi_resource` with `networkSecurityGroup.id` inside `body.properties` (the `azurerm_subnet` + `azurerm_subnet_network_security_group_association` pair is two PUTs and leaves an unprotected gap); Bicep/ARM — set the `networkSecurityGroup` property on the subnet resource; az CLI — pass `--network-security-group` to `az network vnet subnet create`.
6. **Serialize sibling-subnet writes** — ARM serializes writes against the same VNet; parallel writes fail with `AnotherOperationInProgress`. Terraform — list every preceding sibling subnet in `depends_on`. Bicep — rely on the implicit resource graph, or add an explicit `dependsOn` array when siblings live in separate modules. az CLI / scripts — issue creates sequentially.
7. **(Terraform only) Lock the VNet** — add `locks = [data.azurerm_virtual_network.target.id]` to every subnet's `azapi_resource` so Terraform's own parallelism doesn't race ARM in the gap between dependent operations. Bicep/ARM deployments don't need this — the deployment engine doesn't parallelize within one scope.
8. **For PE subnets** — set `privateEndpointNetworkPolicies = "Disabled"` and no delegation. Size the CIDR for the worst-case service that will land on it (some services consume more than one IP per PE — see references).
9. **For App Gateway subnets** — no delegation. If asymmetric routing is observed and your platform allows custom Route Tables, attach one with `0.0.0.0/0 → Internet` (plus any internal corp ranges that must not egress via ExpressRoute / VWAN hub). **BC Gov Landing Zone**: Route Tables are platform-protected (see Step 1) — raise a Public Cloud Service Request for any required UDR.
10. **Expose subnet ID and CIDR as outputs** (Terraform `output`, Bicep `output`, deployment script return value) so downstream stacks can read them via `terraform_remote_state`, Bicep `existing` references, or another state-sharing mechanism.
11. **Validate before apply** — run the tool's validate + dry-run path: Terraform `fmt -recursive`, `validate`, `plan`; Bicep `az bicep build` then `az deployment ... what-if`; ARM `az deployment ... what-if`. Catch CIDR overlap and delegation errors before apply.

## Rules
- Always create the subnet with its NSG attached in the same API call — not as a separate association step. (Why: NSG-at-creation policies deny the gap between subnet PUT and NSG association. Tool specifics: Terraform — `azapi_resource` with `networkSecurityGroup.id` inside `body.properties`; Bicep/ARM — set `networkSecurityGroup` on the subnet itself; az CLI — pass `--network-security-group` to `az network vnet subnet create`.)
- Always serialize sibling-subnet writes against the same VNet. (Why: ARM rejects concurrent subnet PUTs with `AnotherOperationInProgress`. Tool specifics: Terraform — list every preceding sibling subnet in `depends_on`; Bicep — rely on the implicit resource graph or use an explicit `dependsOn` array when siblings are in separate modules; scripts/CLI — create subnets sequentially.)
- Never share a delegated subnet between services. (Why: each subnet allows exactly one `serviceDelegations` entry; the second service errors at associate time.)
- Never set a delegation on a Private Endpoint or App Gateway subnet. (Why: Azure rejects PE creation in delegated subnets, and App Gateway refuses to launch in one.)
- Never move an existing Private Endpoint to a different subnet without a maintenance window. (Why: moving a PE destroys and recreates it, breaking the customer-facing DNS record until propagation completes.)
- Always set `privateEndpointNetworkPolicies = "Disabled"` on PE subnets. (Why: NSG enforcement on PE NICs requires the subnet flag to be off; otherwise PE traffic is silently dropped.)
- Always size PE subnets for the **worst-case** service that will land on them. (Why: Cosmos DB PE consumes 2 IPs — one global + one regional endpoint; Azure AI Services "AIServices" kind exposes up to 3 sub-resources = 3 IPs per PE. A `/27` fills surprisingly fast.)
- Always expose subnet IDs as outputs (Terraform `output`, Bicep `output`) even if no downstream stack reads them yet. (Why: adding outputs later is cheap, but a downstream stack that needs the ID can't read state it isn't exposed to.)
- Never modify VNet address space or create a Private DNS Zone — both are managed centrally by the platform team (see Step 1's platform-protected list; raise a [Public Cloud Service Request](https://citz-do.atlassian.net/servicedesk/customer/portal/3) instead).

## Examples
- "Add a Container Apps Environment subnet" → declare the subnet with a `Microsoft.App/environments` delegation (Terraform `azapi_resource` body, Bicep `delegations` array on the subnet, or `az network vnet subnet create --delegations Microsoft.App/environments`); attach an NSG that allows outbound 443 to AzureContainerRegistry, AzureMonitor, AzureActiveDirectory, and VirtualNetwork; serialize against every other subnet in the VNet.
- "Deployment keeps failing intermittently with `AnotherOperationInProgress`" → sibling subnets are being written in parallel against the same VNet. Terraform — add `depends_on = [azapi_resource.first_subnet]` to the second, and `[azapi_resource.first_subnet, azapi_resource.second_subnet]` to a third. Bicep — add `dependsOn: [first, second]` when siblings span separate modules. CLI — stop backgrounding the `az network vnet subnet create` calls.
- "App Gateway deployment fails with `SubnetMustNotHaveDelegation`" → remove the delegation from the AppGW subnet (Terraform: drop the `delegations` block from the `azapi_resource` body; Bicep: remove the `delegations` array from the subnet; CLI: omit `--delegations`).
- "PE creation fails with `PrivateEndpointCannotBeCreatedInSubnet`" → subnet has a delegation, or `privateEndpointNetworkPolicies` is still `"Enabled"`. Fix both.

## Edge Cases
- **VNet owned by a separate IaC stack** — reference it as an existing resource in the current root (Terraform `data.azurerm_virtual_network`, Bicep `resource ... existing`); pin to its ID for the parent and (Terraform only) for `locks`. Do **not** try to import the VNet.
- **NSG drifts on an existing subnet** — Terraform `azapi_resource` reapplies the NSG ID on every plan because the property lives in the subnet body; `azurerm_subnet` may not surface the drift until the association resource is also reconciled. Bicep redeployments similarly reassert the property since it's declared inline on the subnet.
- **Peered VNet needs direct ingress to a VNet-injected service** without going through App Gateway — add inbound NSG rules on the target subnet at caller-assigned priorities in a reserved band (e.g., 400–499) so adding/removing peers never shifts existing rules.
- **Delegation needs to change on an existing subnet** — Azure returns `SubnetDelegationCannotBeChanged`. The only fix is to destroy and recreate the subnet (Terraform `terraform destroy -target` or `taint`; Bicep — remove from the template and redeploy, then add back; CLI — `az network vnet subnet delete` then re-create). Schedule the outage.

## References
**Platform reference (BC Gov)**: [BC Gov Azure Landing Zone — Networking](https://raw.githubusercontent.com/bcgov/public-cloud-techdocs/refs/heads/main/docs/azure/design-build-deploy/networking.md). Read this first; its rules override any contradictory guidance below.

See [references/REFERENCE.md](./references/REFERENCE.md) for the atomic subnet+NSG body shape in Terraform, Bicep, and az CLI; full NSG rule tables per subnet type; sibling-subnet serialization examples; App Gateway route-table requirements; PE subnet capacity math; and a failure playbook keyed by Azure error code.

For broader Azure topics, prefer these upstream Microsoft skills (in the Microsoft `agent-skills` catalogue — install separately if not already in your agent environment) instead of duplicating their guidance here:
- VNet, hub-spoke, and landing-zone design → `azure-enterprise-infra-planner`
- Workload preparation (Bicep/Terraform scaffolding, azd) → `azure-prepare`
- AKS-specific networking → `azure-kubernetes`
- APIM as AI gateway → `azure-aigateway`
- Pre-deploy validation (preflight, what-if) → `azure-validate`
- Role assignments for services reached over PE → `azure-rbac`
