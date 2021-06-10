param name string
param location string
param key string
param lang string = ''
param extra string = ''
param tags object = {}

resource ssh 'Microsoft.Compute/sshPublicKeys@2020-06-01' = {
  name: name
  location: location
  tags: tags
  properties: {
    publicKey: key
  }
}

output helloword string = 'Hello'
output name string = name
output location string = location
output extra string = extra
output tags object = tags
output lang string = lang
