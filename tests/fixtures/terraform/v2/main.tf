provider "azurerm" {
  skip_provider_registration = true
  features {}
}

resource "azurerm_ssh_public_key" "ssh" {
  name                = var.name
  resource_group_name = var.resource_group
  location            = var.location
  public_key          = var.key
   tags                = var.tags 
}
/* 
resource "azurerm_ssh_public_key" "ssh2" {
  name                = "varname"
  resource_group_name = var.resource_group
  location            = var.location
  public_key          = var.key
  tags                = vasr.tags 
} */

output "hello" {
  value = "v2"
}

output "name" {
  value = azurerm_ssh_public_key.ssh.name
}
