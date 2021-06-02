provider "azurerm" {
  features {}
}

resource "azurerm_ssh_public_key" "ssh" {
  name                = var.name
  resource_group_name = var.resource_group
  location            = var.location
  public_key          = var.key
  tags = {
    Environment = "test"
    Provisioner = "cdf"
  }
}

resource "azurerm_ssh_public_key" "admin" {
  name                = "ssh_admin"
  resource_group_name = var.resource_group
  location            = var.location
  public_key          = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCrs/zJhwDvfjcmXiwlabkZMs7qjA0hl9c3RXBpWYQx2Ps/lhN/I043LsU1zAFPg9P5qaqzVjc73Zky2tZ8qVFKuHAUV8ccwLEwuvWmeqFTK5of6Dt/fuWRbCfpZDcq1nqp+v9bG+OhdNhOUMJFCbFWpHpAP95IOSo9YXeFLdegqMEm8zzgKojYE7RVrrejejmhZcoRMNZj4pxPk/FTqVoTR4C5lzZMBR0XLY/kzq4ay/LfAKyJ+EaNOeFOv/pCIw69DqBDqLiMUwHJLmGkw9azdT6FBXIQhhfeEilItQzfOnzTOh87Xvhv/z0fuhPynUbT6KWX0GO5oTRXE5Xf+TGR"
  tags = {
    Environment = "test"
    Provisioner = "cdf"
  }
}

output "hello" {
  value = "example"
}

output "name" {
  value = azurerm_ssh_public_key.ssh.name
}
