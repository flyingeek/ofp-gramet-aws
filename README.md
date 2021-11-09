# ofp2map-gramet-aws

une fonction lambda tournant sur AWS pour récupérer le GRAMET utilisé par OFP2MAP

## Installation

AWS CLI n'est pas nécessaire, le déploiement se fait par les actions Github (La fonction lambda a été crée au préalable dans la console AWS, avec les réglages nécessaire, y compris la couche python39-requests). Pour tester la fonction localement seul SAM CLI doit être installé (et Docker).

```sh
brew tap aws/tap
brew install aws-sam-cli
```

## Lancer la fonction localement

```sh
sam build
sam local invoke --event events/af084.json
```

ou

```sh
sam build
sam local start-api
open http://127.0.0.1:3000/gramet/0-1632041220-11-327-LFPG_07002_EGXT_03162_03166_EGQK_06012_BGTL_71507_71546_CYQU_KRBL_KSFO__Route_Gramet_AF084_LFPG-KSFO_19Sep21_08_47z_OFP_3_0_1.png
```
