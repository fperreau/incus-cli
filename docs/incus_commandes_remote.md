# Commandes CLI Incus acceptant un préfixe `[remote:]`

> Référence établie à partir des pages de manuel Incus `main`, consultées le 15 juillet 2026. Dans les syntaxes ci-dessous, `[remote:]` désigne le nom facultatif d'un serveur Incus suivi de `:` (par exemple `prod:`). Les options globales disponibles sur toutes les commandes sont : `--debug`, `--explain`, `--force-local`, `-h/--help`, `--project`, `-q/--quiet`, `--sub-commands`, `-v/--verbose`, `--version`.
>
> La colonne **Options** recense les options spécifiques les plus directement exposées par la commande ; `--help` reste la référence normative de la version installée.

| Domaine | Commande | Syntaxe de la commande CLI | Description courte | Liste des options |
|---|---|---|---|---|
| Instance | list | incus list [remote:] [filters...] | Liste les conteneurs et machines virtuelles du serveur ciblé. | `-c/--columns`, `-f/--format`, `--fast`, `--all-projects`, `--project`, `--target` |
| Instance | info | incus info [remote:][instance] | Affiche les informations du serveur ou d'une instance. | `--show-log`, `--resources`, `--target`, `--project` |
| Instance | create | incus create [remote:]image [remote:]instance | Crée une instance sans la démarrer. | `-c/--config`, `-d/--device`, `-p/--profile`, `-n/--network`, `-s/--storage`, `--type`, `--target`, `--empty`, `--vm`, `--no-profiles` |
| Instance | launch | incus launch [remote:]image [remote:]instance | Crée et démarre une instance. | `-c/--config`, `-d/--device`, `-p/--profile`, `-n/--network`, `-s/--storage`, `--type`, `--target`, `--vm`, `--no-profiles`, `--console` |
| Instance | copy | incus copy [remote:]source [remote:]destination | Copie une instance localement ou entre serveurs. | `--config`, `--device`, `--mode`, `--profile`, `--refresh`, `--instance-only`, `--allow-inconsistent`, `--target`, `--storage` |
| Instance | move | incus move [remote:]source [remote:]destination | Déplace ou renomme une instance, y compris entre serveurs. | `--config`, `--device`, `--mode`, `--profile`, `--instance-only`, `--target`, `--storage` |
| Instance | delete | incus delete [remote:]instance... | Supprime une ou plusieurs instances. | `-f/--force`, `-i/--interactive`, `--target` |
| Instance | start | incus start [remote:]instance... | Démarre une ou plusieurs instances. | `--all`, `--console`, `--stateless`, `--target` |
| Instance | stop | incus stop [remote:]instance... | Arrête une ou plusieurs instances. | `--all`, `-f/--force`, `--stateful`, `-t/--timeout`, `--target` |
| Instance | restart | incus restart [remote:]instance... | Redémarre une ou plusieurs instances. | `--all`, `-f/--force`, `-t/--timeout`, `--target` |
| Instance | pause | incus pause [remote:]instance... | Suspend l'exécution d'instances. | `--all`, `--target` |
| Instance | resume | incus resume [remote:]instance... | Reprend l'exécution d'instances suspendues. | `--all`, `--target` |
| Instance | rebuild | incus rebuild [remote:]image [remote:]instance | Reconstruit une instance à partir d'une image. | `--empty`, `--force`, `--target` |
| Instance | rename | incus rename [remote:]instance nouveau-nom | Renomme une instance sur le serveur ciblé. | `--target` |
| Instance | exec | incus exec [remote:]instance -- commande [arguments...] | Exécute une commande dans une instance. | `--cwd`, `--env`, `--group`, `--mode`, `--user`, `--disable-stdin`, `--force-interactive`, `--force-noninteractive` |
| Instance | console | incus console [remote:]instance | Ouvre une console d'instance. | `--show-log`, `--type`, `--console`, `--target` |
| Instance | export | incus export [remote:]instance [fichier] | Exporte une sauvegarde d'instance. | `--instance-only`, `--optimized-storage`, `--compression`, `--target` |
| Instance | publish | incus publish [remote:]instance[/snapshot] [remote:] [flags] | Publie une instance ou un instantané comme image. | `--alias`, `--compression`, `--expire`, `--force`, `--public`, `--reuse`, `--type` |
| Instance | wait | incus wait [remote:]instance | Attend qu'une condition d'instance soit satisfaite. | `--condition`, `--timeout` |
| Instance | top | incus top [remote:] | Affiche l'utilisation des ressources par instance. | `--all-projects`, `--columns`, `--format`, `--refresh`, `--project` |
| Serveur | version | incus version [remote:] | Affiche les versions du client et du serveur. | Options globales uniquement |
| Serveur | monitor | incus monitor [remote:] | Suit les événements d'un serveur local ou distant. | `--pretty`, `--type` |
| Serveur | query | incus query [remote:]chemin-API | Envoie une requête brute à l'API Incus. | `-d/--data`, `-X/--request`, `--wait`, `--target`, `--raw` |
| Serveur | webui | incus webui [remote:] | Ouvre l'interface Web du serveur ciblé. | Options globales uniquement |
| Snapshot | create | incus snapshot create [remote:]instance [snapshot] | Crée un instantané d'instance. | `--no-expiry`, `--reuse`, `--stateful`, `--expiry` |
| Snapshot | delete | incus snapshot delete [remote:]instance snapshot... | Supprime des instantanés d'instance. | `-i/--interactive` |
| Snapshot | list | incus snapshot list [remote:]instance | Liste les instantanés d'une instance. | `-c/--columns`, `-f/--format` |
| Snapshot | rename | incus snapshot rename [remote:]instance ancien nouveau | Renomme un instantané. | Options globales uniquement |
| Snapshot | restore | incus snapshot restore [remote:]instance snapshot | Restaure un instantané d'instance. | `--stateful` |
| Snapshot | show | incus snapshot show [remote:]instance snapshot | Affiche la configuration d'un instantané. | Options globales uniquement |
| Fichier | create | incus file create [remote:]instance/chemin... | Crée des fichiers ou répertoires dans une instance. | `--type`, `--mode`, `--uid`, `--gid` |
| Fichier | delete | incus file delete [remote:]instance/chemin... | Supprime des fichiers dans une instance. | `-r/--recursive` |
| Fichier | edit | incus file edit [remote:]instance/chemin | Modifie un fichier dans une instance. | Options globales uniquement |
| Fichier | mount | incus file mount [remote:]instance/chemin chemin-local | Monte localement un chemin d'instance. | `--listen`, `--auth`, `--uid`, `--gid` |
| Fichier | pull | incus file pull [remote:]instance/chemin... destination | Copie des fichiers depuis une instance. | `-p/--create-dirs`, `-r/--recursive`, `--uid`, `--gid`, `--mode` |
| Fichier | push | incus file push source... [remote:]instance/chemin | Copie des fichiers vers une instance. | `-p/--create-dirs`, `-r/--recursive`, `--uid`, `--gid`, `--mode` |
| Image | list | incus image list [remote:] [filtres...] | Liste les images disponibles sur un serveur ou serveur d'images. | `-c/--columns`, `-f/--format` |
| Image | info | incus image info [remote:]image | Affiche les informations détaillées d'une image. | Options globales uniquement |
| Image | show | incus image show [remote:]image | Affiche les propriétés YAML d'une image. | Options globales uniquement |
| Image | edit | incus image edit [remote:]image | Modifie les propriétés d'une image. | Options globales uniquement |
| Image | delete | incus image delete [remote:]image... | Supprime une ou plusieurs images. | Options globales uniquement |
| Image | copy | incus image copy [remote:]image [remote:] | Copie une image entre serveurs. | `--alias`, `--auto-update`, `--copy-aliases`, `--mode`, `--public`, `--target-project`, `--type` |
| Image | export | incus image export [remote:]image [destination] | Exporte et télécharge une image. | Options globales uniquement |
| Image | refresh | incus image refresh [remote:]image | Actualise une image mise en cache. | Options globales uniquement |
| Image | get-property | incus image get-property [remote:]image clé | Lit une propriété d'image. | Options globales uniquement |
| Image | set-property | incus image set-property [remote:]image clé=valeur... | Définit des propriétés d'image. | Options globales uniquement |
| Image | unset-property | incus image unset-property [remote:]image clé... | Supprime des propriétés d'image. | Options globales uniquement |
| Réseau | list | incus network list [remote:] | Liste les réseaux du serveur ciblé. | `-c/--columns`, `-f/--format`, `--target` |
| Réseau | create | incus network create [remote:]réseau [clé=valeur...] | Crée un réseau. | `--target`, `--type` |
| Réseau | delete | incus network delete [remote:]réseau | Supprime un réseau. | `--target` |
| Réseau | show | incus network show [remote:]réseau | Affiche la configuration d'un réseau. | `--target` |
| Réseau | edit | incus network edit [remote:]réseau | Modifie la configuration YAML d'un réseau. | `--target` |
| Réseau | get | incus network get [remote:]réseau clé | Lit une clé de configuration réseau. | `--property`, `--target` |
| Réseau | set | incus network set [remote:]réseau clé=valeur... | Définit des clés de configuration réseau. | `--property`, `--target` |
| Réseau | unset | incus network unset [remote:]réseau clé... | Supprime des clés de configuration réseau. | `--property`, `--target` |
| Réseau | info | incus network info [remote:]réseau | Affiche les informations d'exécution d'un réseau. | `--target` |
| Réseau | list-allocations | incus network list-allocations [remote:] | Liste les allocations réseau utilisées. | `-f/--format` |
| Réseau | list-leases | incus network list-leases [remote:]réseau | Liste les baux DHCP d'un réseau. | `-f/--format`, `--target` |
| Stockage | list | incus storage list [remote:] | Liste les pools de stockage. | `-c/--columns`, `-f/--format`, `--target` |
| Stockage | create | incus storage create [remote:]pool pilote [clé=valeur...] | Crée un pool de stockage. | `--target` |
| Stockage | delete | incus storage delete [remote:]pool | Supprime un pool de stockage. | `--target` |
| Stockage | show | incus storage show [remote:]pool | Affiche configuration et ressources du pool. | `--resources`, `--target` |
| Stockage | info | incus storage info [remote:]pool | Affiche les informations utiles d'un pool. | `--bytes`, `--target` |
| Stockage | edit | incus storage edit [remote:]pool | Modifie la configuration YAML d'un pool. | `--target` |
| Stockage | get | incus storage get [remote:]pool clé | Lit une clé de configuration du pool. | `--property`, `--target` |
| Stockage | set | incus storage set [remote:]pool clé=valeur... | Définit des clés de configuration du pool. | `--property`, `--target` |
| Stockage | unset | incus storage unset [remote:]pool clé... | Supprime des clés de configuration du pool. | `--property`, `--target` |
| Volume | list | incus storage volume list [remote:]pool | Liste les volumes d'un pool. | `-c/--columns`, `-f/--format`, `--all-projects`, `--target` |
| Volume | create | incus storage volume create [remote:]pool volume [clé=valeur...] | Crée un volume de stockage. | `--type`, `--target` |
| Volume | delete | incus storage volume delete [remote:]pool volume | Supprime un volume de stockage. | `--target` |
| Volume | show | incus storage volume show [remote:]pool volume | Affiche la configuration d'un volume. | `--target` |
| Volume | copy | incus storage volume copy [remote:]pool/volume [remote:]pool/volume | Copie un volume, éventuellement entre serveurs. | `--mode`, `--refresh`, `--volume-only`, `--target`, `--target-project` |
| Volume | move | incus storage volume move [remote:]pool/volume [remote:]pool/volume | Déplace ou renomme un volume. | `--mode`, `--volume-only`, `--target`, `--target-project` |
| Profil | list | incus profile list [remote:] | Liste les profils. | `-c/--columns`, `-f/--format` |
| Profil | create | incus profile create [remote:]profil | Crée un profil. | Options globales uniquement |
| Profil | copy | incus profile copy [remote:]profil [remote:][profil] | Copie un profil localement ou entre serveurs. | `--refresh`, `--target-project` |
| Profil | delete | incus profile delete [remote:]profil... | Supprime des profils. | Options globales uniquement |
| Profil | show | incus profile show [remote:]profil | Affiche la configuration d'un profil. | Options globales uniquement |
| Profil | edit | incus profile edit [remote:]profil | Modifie la configuration YAML d'un profil. | Options globales uniquement |
| Profil | get | incus profile get [remote:]profil clé | Lit une clé de profil. | `--property` |
| Profil | set | incus profile set [remote:]profil clé=valeur... | Définit des clés ou propriétés de profil. | `--property` |
| Profil | unset | incus profile unset [remote:]profil clé... | Supprime des clés ou propriétés de profil. | `--property` |
| Projet | list | incus project list [remote:] | Liste les projets. | `-c/--columns`, `-f/--format` |
| Projet | create | incus project create [remote:]projet | Crée un projet. | Options globales uniquement |
| Projet | delete | incus project delete [remote:]projet | Supprime un projet. | Options globales uniquement |
| Projet | show | incus project show [remote:]projet | Affiche les options d'un projet. | Options globales uniquement |
| Projet | info | incus project info [remote:]projet | Affiche un résumé des allocations du projet. | Options globales uniquement |
| Projet | get | incus project get [remote:]projet clé | Lit une clé de configuration de projet. | `--property` |
| Projet | set | incus project set [remote:]projet clé=valeur... | Définit des clés de configuration du projet. | `--property` |
| Projet | unset | incus project unset [remote:]projet clé... | Supprime des clés de configuration du projet. | `--property` |
| Cluster | list | incus cluster list [remote:] | Liste les membres du cluster. | `-c/--columns`, `-f/--format` |
| Cluster | show | incus cluster show [remote:]membre | Affiche les détails d'un membre. | Options globales uniquement |
| Cluster | info | incus cluster info [remote:]membre | Affiche les informations utiles d'un membre. | Options globales uniquement |
| Cluster | add | incus cluster add [remote:]nom | Génère un jeton d'ajout de membre. | Options globales uniquement |
| Cluster | remove | incus cluster remove [remote:]membre | Retire un membre du cluster. | `-f/--force` |
| Opération | list | incus operation list [remote:] | Liste les opérations d'arrière-plan. | `-f/--format` |
| Opération | show | incus operation show [remote:]UUID | Affiche une opération d'arrière-plan. | Options globales uniquement |
| Opération | delete | incus operation delete [remote:]UUID | Annule puis supprime une opération. | Options globales uniquement |
| Avertissement | list | incus warning list [remote:] | Liste les avertissements. | `-c/--columns`, `-f/--format`, `--all-projects` |
| Avertissement | show | incus warning show [remote:]UUID | Affiche un avertissement. | Options globales uniquement |
| Avertissement | acknowledge | incus warning acknowledge [remote:]UUID | Acquitte un avertissement. | Options globales uniquement |
| Avertissement | delete | incus warning delete [remote:]UUID | Supprime un avertissement. | Options globales uniquement |

## Remarques

- Certaines familles possèdent des sous-commandes supplémentaires (`network acl`, `network forward`, `network peer`, `network zone`, `storage bucket`, `storage volume snapshot`, `cluster group`, etc.). Elles suivent généralement le même adressage `[remote:]objet`.
- Un remote d'images Simple Streams ou OCI n'accepte qu'un sous-ensemble des commandes d'images. Les commandes de gestion du serveur, des instances, du stockage ou du réseau exigent un remote de protocole `incus`.
- Pour vérifier la syntaxe et toutes les options disponibles dans la version réellement installée, utiliser `incus <commande> --help` ou `incus manpage`.

## Sources

- Documentation générale Incus : https://linuxcontainers.org/incus/docs/main/
- Pages de manuel CLI : https://linuxcontainers.org/incus/docs/main/reference/manpages/incus/
- Gestion des images distantes : https://linuxcontainers.org/incus/docs/main/howto/images_remote/
