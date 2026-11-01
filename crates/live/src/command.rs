// -------------------------------------------------------------------------------------------------
//  Copyright (C) 2015-2026 Nautech Systems Pty Ltd. All rights reserved.
//  https://nautechsystems.io
//
//  Licensed under the GNU Lesser General Public License Version 3.0 (the "License");
//  You may not use this file except in compliance with the License.
//  You may obtain a copy of the License at https://www.gnu.org/licenses/lgpl-3.0.en.html
//
//  Unless required by applicable law or agreed to in writing, software
//  distributed under the License is distributed on an "AS IS" BASIS,
//  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
//  See the License for the specific language governing permissions and
//  limitations under the License.
// -------------------------------------------------------------------------------------------------

//! Commands for the live node's event loop.

use std::fmt::Debug;

use nautilus_model::identifiers::ClientId;

use crate::execution::client::LiveExecutionClient;

/// Response type for lifecycle commands: `Ok(())` or error message.
pub type LifecycleCommandResponse = Result<(), String>;

/// Commands for execution client lifecycle management routed through the live node's event loop.
pub enum ExecClientCommand {
    /// Add a new execution client to the running node.
    Add(Box<LiveExecutionClient>, tokio::sync::oneshot::Sender<LifecycleCommandResponse>),
    /// Remove an execution client by its ID.
    Remove(ClientId, tokio::sync::oneshot::Sender<LifecycleCommandResponse>),
}

impl Debug for ExecClientCommand {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Add(client, _) => f.debug_tuple("Add").field(client).finish(),
            Self::Remove(client_id, _) => f.debug_tuple("Remove").field(client_id).finish(),
        }
    }
}
