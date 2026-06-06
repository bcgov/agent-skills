# azure-networking — Deep Reference

Supplementary detail for [SKILL.md](../SKILL.md). Read the manifest first for the operational overview.

This reference covers concrete IaC patterns (Terraform, Bicep, az CLI) for Azure subnets, NSGs, and private endpoints. Snippets are illustrative — adapt names, prefixes, and modules to your repo. All CIDRs are placeholders.

---

## Atomic Subnet + NSG Creation

The API surface matters. Any tool that creates the subnet first and then attaches the NSG as a separate operation hits an intermediate state that NSG-at-creation policies reject. The fix is to send the NSG ID inside the body of the subnet PUT itself.

### Terraform — `azapi_resource`

`azurerm_subnet` + `azurerm_subnet_network_security_group_association` is two API calls. `azapi_resource` lets you put the NSG (and route table, and delegation) into the body of the same PUT.

```hcl
resource "azapi_resource" "pe_subnet" {
  type      = "Microsoft.Network/virtualNetworks/subnets@2024-01-01"
  name      = "privateendpoints-subnet"
  parent_id = data.azurerm_virtual_network.target.id
  locks     = [data.azurerm_virtual_network.target.id]

  body = {
    properties = {
      addressPrefix                  = "10.0.0.0/27"
      privateEndpointNetworkPolicies = "Disabled"
      networkSecurityGroup           = { id = azurerm_network_security_group.pe.id }
      # NO delegations block for PE subnets
    }
  }

  depends_on = [
    # Every preceding sibling subnet in this VNet.
  ]
}
```

For a VNet-injected service such as Container Apps Environment, add a delegation block:

```hcl
body = {
  properties = {
    addressPrefix        = "10.0.0.64/27"
    networkSecurityGroup = { id = azurerm_network_security_group.aca.id }
    delegations = [{
      name       = "Microsoft.App/environments"
      properties = { serviceName = "Microsoft.App/environments" }
    }]
  }
}
```

### Bicep / ARM

Bicep and ARM let you declare `networkSecurityGroup` directly on the subnet — there is no separate association resource. Declaring the subnet as a child of an `existing` VNet keeps the parent reference explicit.

```bicep
resource vnet 'Microsoft.Network/virtualNetworks@2024-01-01' existing = {
  name: vnetName
  scope: resourceGroup(vnetResourceGroup)
}

resource peNsg 'Microsoft.Network/networkSecurityGroups@2024-01-01' = {
  name: 'nsg-pe'
  location: location
  properties: { securityRules: [] } // tighten in production
}

resource peSubnet 'Microsoft.Network/virtualNetworks/subnets@2024-01-01' = {
  parent: vnet
  name: 'privateendpoints-subnet'
  properties: {
    addressPrefix: '10.0.0.0/27'
    privateEndpointNetworkPolicies: 'Disabled'
    networkSecurityGroup: { id: peNsg.id }
    // no delegations for PE subnets
  }
}
```

For a VNet-injected service:

```bicep
resource acaSubnet 'Microsoft.Network/virtualNetworks/subnets@2024-01-01' = {
  parent: vnet
  name: 'aca-subnet'
  properties: {
    addressPrefix: '10.0.0.64/27'
    networkSecurityGroup: { id: acaNsg.id }
    delegations: [
      {
        name: 'Microsoft.App/environments'
        properties: { serviceName: 'Microsoft.App/environments' }
      }
    ]
  }
}
```

### az CLI

The CLI accepts the NSG and delegation as flags on the create call, so the subnet is born with both attached:

```bash
az network vnet subnet create \
  --resource-group <rg> \
  --vnet-name <vnet> \
  --name privateendpoints-subnet \
  --address-prefixes 10.0.0.0/27 \
  --network-security-group <nsg-id-or-name> \
  --disable-private-endpoint-network-policies true
```

For a delegated subnet:

```bash
az network vnet subnet create \
  --resource-group <rg> \
  --vnet-name <vnet> \
  --name aca-subnet \
  --address-prefixes 10.0.0.64/27 \
  --network-security-group <aca-nsg> \
  --delegations Microsoft.App/environments
```

### Subnet purpose → delegation reference

| Subnet purpose                                | Delegation                            | `privateEndpointNetworkPolicies` |
|-----------------------------------------------|---------------------------------------|----------------------------------|
| Private Endpoints                             | none                                  | `"Disabled"`                     |
| App Gateway                                   | none                                  | default                          |
| APIM (internal mode, stv2)                    | none                                  | default                          |
| Container Apps Environment                    | `Microsoft.App/environments`          | default                          |
| App Service / Functions VNet integration      | `Microsoft.Web/serverFarms`           | default                          |
| AKS node pool (kubenet / Azure CNI)           | none                                  | default                          |

Always confirm the current required delegation in the service's own Microsoft Learn docs before adding one — Azure occasionally introduces new delegations or deprecates old names.

---

## Serializing Sibling Subnet Writes

ARM serializes writes against the same VNet — concurrent subnet PUTs fail with `AnotherOperationInProgress`.

### Terraform

Each subnet must depend on **all** preceding siblings:

```
azapi_resource.pe_subnet                  # no deps (first)
azapi_resource.apim_subnet                # depends_on: [pe_subnet]
azapi_resource.appgw_subnet               # depends_on: [pe_subnet, apim_subnet]
azapi_resource.aca_subnet                 # depends_on: [pe_subnet, apim_subnet, appgw_subnet]
```

Combine the chain with `locks = [data.azurerm_virtual_network.target.id]` on every subnet so Terraform's own parallelism doesn't race ARM in the small window between dependent operations.

### Bicep

Within one Bicep deployment, the resource graph usually serializes writes via implicit dependencies — if `subnetB` references `subnetA.id`, ARM creates them in order. When siblings have no natural reference, add explicit `dependsOn`:

```bicep
resource apimSubnet 'Microsoft.Network/virtualNetworks/subnets@2024-01-01' = {
  parent: vnet
  name: 'apim-subnet'
  dependsOn: [ peSubnet ]
  properties: { /* ... */ }
}
```

When subnets live in separate modules deployed by the same parent, chain the modules with `dependsOn` arrays so ARM doesn't dispatch them in parallel.

### az CLI / scripts

Issue `az network vnet subnet create` calls **sequentially**. Don't background them and don't fan them out with `xargs -P` or PowerShell `ForEach-Object -Parallel`.

---

## Private Endpoint Subnet Capacity

- Azure reserves 5 IPs per subnet (network, gateway, DNS x2, broadcast). A `/24` yields ~251 usable IPs; a `/27` yields ~27.
- Per-PE IP cost varies by service:

| Service                                  | IPs per PE         | Notes                                                          |
|------------------------------------------|--------------------|----------------------------------------------------------------|
| Most single-sub-resource services        | 1                  | One IP for one sub-resource (e.g., Key Vault, single Blob).    |
| Cosmos DB (SQL API)                      | 2                  | Global endpoint + one regional endpoint per region.            |
| Azure AI Services (`AIServices` kind)    | up to 3            | Exposes `cognitiveservices`, `openai`, and `services.ai`.      |
| Storage Account                          | 1 per sub-resource | One PE per `blob` / `file` / `queue` / `table` you enable.     |

Size the subnet for the worst-case workload that will land on it and add headroom for growth before it runs out of IPs — moving a PE later is destructive (PE recreate + DNS repropagation).

---

## NSG Rule Reference Layouts

Starting points, not contracts. Tighten priorities and ranges to your actual upstream/downstream traffic.

### PE subnet NSG

| Priority | Direction | Source / Destination                          | Port | Purpose                              |
|----------|-----------|-----------------------------------------------|------|--------------------------------------|
| 100+     | Inbound   | each consuming VNet address space → PE CIDRs  | 443  | Allow callers reaching PEs           |
| 200+     | Outbound  | PE CIDRs → each consuming VNet address space  | 443  | PE responses (NSG stateful — often optional) |

### APIM subnet NSG (internal mode, stv2)

| Priority | Direction | Source / Destination               | Port      | Purpose                          |
|----------|-----------|------------------------------------|-----------|----------------------------------|
| 100      | Inbound   | `ApiManagement` service tag        | 3443      | APIM control plane               |
| 110      | Inbound   | `AzureLoadBalancer` service tag    | *         | LB health probes                 |
| 400–499  | Inbound   | peered VNets (caller-assigned)     | 443       | Direct ingress from peers        |
| 100      | Outbound  | `Storage` service tag              | 443       | APIM artifact storage            |
| 110      | Outbound  | `AzureKeyVault` service tag        | 443       | Backend secrets                  |
| 120      | Outbound  | `VirtualNetwork`                   | 443       | PE access to other Azure services |
| 130      | Outbound  | `AzureActiveDirectory` service tag | 443       | Token validation                 |

Reserve a priority band (e.g. 400–499) for dynamic peer entries so adding or removing a peer never shifts existing rules.

### App Gateway subnet NSG

| Priority | Direction | Source / Destination               | Port        | Purpose                       |
|----------|-----------|------------------------------------|-------------|-------------------------------|
| 100      | Inbound   | `Internet`                         | 443         | HTTPS ingress                 |
| 120      | Inbound   | `GatewayManager` service tag       | 65200–65535 | AGW infrastructure control    |
| 130      | Inbound   | `AzureLoadBalancer` service tag    | *           | LB health probes              |

Port 80 is intentionally not allowed — let App Gateway terminate HTTPS and skip an HTTP-to-HTTPS hop at the NSG layer.

### Container Apps Environment subnet NSG

| Priority | Direction | Source / Destination                  | Port  | Purpose                       |
|----------|-----------|---------------------------------------|-------|-------------------------------|
| 100      | Outbound  | `AzureContainerRegistry` service tag  | 443   | Pull images                   |
| 110      | Outbound  | `AzureMonitor` service tag            | 443   | Logs / metrics                |
| 120      | Outbound  | `AzureActiveDirectory` service tag    | 443   | Managed identity tokens       |
| 130      | Outbound  | `VirtualNetwork`                      | 443   | PE access                     |
| 200+     | Inbound   | each consuming VNet address space     | *     | App-specific ingress          |

---

## App Gateway Route Table (Asymmetric Routing Fix)

App Gateway is one of the few subnets that often needs an explicit route table — typically a `0.0.0.0/0 → Internet` route to override a UDR that a hub-spoke topology applies at the VNet level, plus any internal corp ranges that must NOT egress through ExpressRoute / VWAN.

**BC Gov Landing Zone**: Route Tables are platform-protected (see SKILL.md Step 1 and the final Rule) — do **not** attach your own. Raise a [Public Cloud Service Request](https://citz-do.atlassian.net/servicedesk/customer/portal/3) describing the required UDRs (destination prefix, next-hop type, next-hop IP); the Azure Landing Zone platform team owns the create / update.

---

## Common Pitfalls

| Pitfall                                                       | Consequence                                                  | Prevention                                                  |
|---------------------------------------------------------------|--------------------------------------------------------------|-------------------------------------------------------------|
| Reusing a PE subnet for VNet integration                      | Service deploy fails — PE subnet has no delegation           | Always create a dedicated delegated subnet                  |
| Sharing one delegated subnet between two services             | Second service fails to associate                            | One delegation per subnet, period                           |
| CIDR not fully inside the parent address space                | `terraform plan` validation fails                            | Confirm the inner CIDR fits the outer map key               |
| Duplicate subnet name across address spaces                   | Map merge collides; plan fails                               | Each subnet name appears in exactly one address space       |
| Missing `depends_on` in subnet chain                          | Intermittent `AnotherOperationInProgress`                    | Chain every preceding sibling subnet                        |
| Creating the subnet and attaching the NSG as separate operations | Policy denial during the association gap                  | Attach the NSG inline at creation (Terraform `azapi_resource` body, Bicep `networkSecurityGroup` property, CLI `--network-security-group`) |
| Forgetting an output for a new subnet ID                      | Downstream stack can't reference it                          | Add the output up front, even if no consumer exists yet     |
| Setting any delegation on the App Gateway subnet              | AGW deployment rejected                                      | App Gateway subnet must have **no** delegation              |
| Changing PE subnet assignment after first deploy              | All PEs in the workload recreate; DNS gap until repropagation | Freeze the assignment in workload config                    |

---

## Failure Playbook

| Symptom                                            | Likely cause                                                                       | Fix                                                                                |
|----------------------------------------------------|------------------------------------------------------------------------------------|------------------------------------------------------------------------------------|
| `SubnetMustNotHaveDelegation`                      | Delegation set on a PE or App Gateway subnet                                       | Remove `delegations` from the subnet (Terraform `azapi_resource` body, Bicep `delegations` array, CLI omit `--delegations`) |
| `SubnetDelegationCannotBeChanged`                  | Tried to change delegation on an existing subnet                                   | Destroy and recreate the subnet (Terraform `terraform destroy -target` or `taint`; Bicep — remove from template, redeploy, then add back; CLI — `az network vnet subnet delete` then re-create) |
| `NetworkSecurityGroupNotAssociated`                | Subnet created without an NSG in its body under an NSG-at-creation policy           | Attach the NSG inline at creation (Terraform `azapi_resource` with `networkSecurityGroup.id` in `body.properties`; Bicep `networkSecurityGroup` property on the subnet; CLI `--network-security-group`) |
| `SubnetConflictWithOtherSubnet`                    | CIDR overlap within the same address space                                         | Re-check the allocation map; pick non-overlapping CIDRs                            |
| `AnotherOperationInProgress`                       | Concurrent subnet PUTs to the same VNet                                            | Serialize subnet writes (Terraform `depends_on` chain + `locks`; Bicep `dependsOn` across modules; CLI — sequential calls) |
| `PrivateEndpointCannotBeCreatedInSubnet`           | Subnet has a delegation, or `privateEndpointNetworkPolicies` is not `"Disabled"`   | Fix both on the subnet                                                             |
