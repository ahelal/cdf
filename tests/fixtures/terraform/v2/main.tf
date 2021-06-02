provider "azurerm" {
  features {}
}

resource "azurerm_ssh_public_key" "ssh" {
  name                = var.name
  resource_group_name = var.resource_group
  location            = var.location
  public_key          = var.key
  tags                = var.tags
}

output "hello" {
  value = "example"
}

output "name" {
  value = azurerm_ssh_public_key.ssh.name
}
