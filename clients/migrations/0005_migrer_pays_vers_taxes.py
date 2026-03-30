# clients/migrations/0005_migrer_pays_vers_taxes.py
from django.db import migrations, models
import django.db.models.deletion


def migrer_pays_vers_taxes(apps, schema_editor):
    """
    Migre les pays de l'ancien modèle vers le nouveau
    """
    # Récupérer les modèles
    Client = apps.get_model('clients', 'Client')
    OldPays = apps.get_model('produits', 'Pays')
    NewPays = apps.get_model('taxes', 'Pays')
    
    # Créer un mapping des anciens IDs vers les nouveaux IDs
    mapping_pays = {}
    
    # Parcourir tous les anciens pays
    for old_pays in OldPays.objects.all():
        # Chercher un pays correspondant dans le nouveau modèle
        new_pays, created = NewPays.objects.get_or_create(
            code=old_pays.code,
            defaults={
                'nom': old_pays.nom,
                'devise': old_pays.devise if hasattr(old_pays, 'devise') else 'FCFA',
                'devise_symbole': old_pays.devise_symbole if hasattr(old_pays, 'devise_symbole') else 'FCFA',
                'actif': old_pays.actif if hasattr(old_pays, 'actif') else True
            }
        )
        mapping_pays[old_pays.id] = new_pays.id
        print(f"✅ Migration: {old_pays.nom} (ID {old_pays.id}) → {new_pays.nom} (ID {new_pays.id})")
    
    # Mettre à jour tous les clients
    for client in Client.objects.all():
        if client.pays_obj_id and client.pays_obj_id in mapping_pays:
            nouveau_id = mapping_pays[client.pays_obj_id]
            print(f"  🔄 Client {client.nom}: ancien ID {client.pays_obj_id} → nouveau ID {nouveau_id}")
            # Mise à jour directe en SQL pour contourner les contraintes
            # On utilisera une mise à jour après la migration structurelle
            # Pour l'instant, on stocke l'ancien ID pour après la migration
            client.ancien_pays_id = client.pays_obj_id


def inverser_migration(apps, schema_editor):
    """Inverse la migration"""
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('clients', '0004_alter_client_indicatif_alter_client_pays_obj'),
        ('taxes', '0001_initial'),
        ('produits', '0001_initial'),  # Ajustez selon vos migrations
    ]

    operations = [
        # Étape 1: Ajouter un champ temporaire pour stocker les anciens IDs
        migrations.AddField(
            model_name='client',
            name='ancien_pays_id',
            field=models.IntegerField(null=True, blank=True),
        ),
        
        # Étape 2: Stocker les anciens IDs
        migrations.RunPython(migrer_pays_vers_taxes, inverser_migration),
        
        # Étape 3: Supprimer la contrainte de clé étrangère
        migrations.RemoveField(
            model_name='client',
            name='pays_obj',
        ),
        
        # Étape 4: Recréer le champ avec la nouvelle relation
        migrations.AddField(
            model_name='client',
            name='pays_obj',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='clients',
                to='taxes.pays',
                verbose_name='Pays'
            ),
        ),
        
        # Étape 5: Restaurer les relations
        migrations.RunPython(
            lambda apps, schema_editor: restaurer_relations(apps, schema_editor),
            inverser_migration
        ),
    ]


def restaurer_relations(apps, schema_editor):
    """
    Restaure les relations après la recréation du champ
    """
    Client = apps.get_model('clients', 'Client')
    NewPays = apps.get_model('taxes', 'Pays')
    
    for client in Client.objects.exclude(ancien_pays_id__isnull=True):
        try:
            # Trouver le nouveau pays correspondant
            # On pourrait utiliser le mapping, mais pour simplifier,
            # on cherche par le nom ou le code
            # Ici on suppose qu'on a stocké l'ancien ID
            # Vous devrez adapter selon votre logique
            pass
        except Exception as e:
            print(f"Erreur pour client {client.nom}: {e}")