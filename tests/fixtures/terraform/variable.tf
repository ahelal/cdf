variable "name" {
  type = string
}

variable "resource_group" {
  type = string
}

variable "location" {
  type = string
}

variable "key" {
  type = string
}

variable "tags" {
  type = map(any)
  default = {
    Environment = "test"
    Provisioner = "cdf"
  }
}
