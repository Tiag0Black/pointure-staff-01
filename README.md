# STAFF MANAGEMENT

Site indépendant de pointage STAFF, sans compte et sans mot de passe.

## Fonctions
- Saisie du nom et choix du grade.
- Boutons « LANCER MON SERVICE » et « ARRÊTER MON SERVICE ».
- Enregistrement automatique des heures de début et de fin.
- Calcul de la durée de chaque service.
- Tableau général public de tous les membres.
- Historique individuel public.
- Classement et total hebdomadaire (lundi au dimanche).
- Export CSV public.
- Heures affichées au fuseau de Paris.

## Mise en ligne sur GitHub et Render
1. Décompresser le ZIP.
2. Créer un dépôt GitHub et téléverser tous les fichiers et dossiers.
3. Dans Render, choisir **New + → Blueprint**, puis sélectionner ce dépôt.
4. Render détectera `render.yaml` et créera le service web.
5. Créer une base PostgreSQL (Neon convient) et copier sa chaîne de connexion.
6. Dans Render → service web → Environment, créer `DATABASE_URL` et coller la chaîne de connexion PostgreSQL. Le projet utilise Psycopg 3.
7. Vérifier que `SECRET_KEY` est défini (Render le génère avec le Blueprint ci-dessus).
8. Déployer.

Important : PostgreSQL est nécessaire en production pour conserver les pointages après les redémarrages. Ne pas utiliser SQLite sur le disque éphémère de Render.

## Adresses du site
- Pointage : `/`
- Tableau général : `/admin`
- Historique individuel : `/historique?name=Nom`
- Export CSV : `/admin/export.csv`

## Important
Tout est public, sans mot de passe. Comme il n'y a pas de compte individuel, n'importe qui peut saisir le nom d'un autre staff et consulter son historique ou arrêter son service. Les noms et grades saisis ne sont pas vérifiés.
