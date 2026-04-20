/*
    Orphan.cs — deliberately imports two CatalystCore namespaces NOT
    declared anywhere in this fixture. Drives the unresolved-using proof.

    UNRESOLVED expected:
      - CatalystCore.Models.Data
      - CatalystCore.MissingModule

    External (ignored by the datum):
      - UnityEngine
*/

using CatalystCore.Models.Data;
using CatalystCore.MissingModule;
using UnityEngine;

namespace CatalystCore.Sample.Orphan
{
    public class OrphanHolder
    {
        public int id;
    }
}
