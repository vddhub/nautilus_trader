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
#[cfg(feature = "python")]
use nautilus_model::identifiers::StrategyId;
#[cfg(feature = "python")]
use pyo3::{Py, PyAny};

use crate::execution::client::LiveExecutionClient;

/// Response type for lifecycle commands: `Ok(())` or error message.
pub type LifecycleCommandResponse = Result<(), String>;

/// Commands for component lifecycle management routed through the live node's event loop.
///
/// Each variant carries a oneshot reply sender so the caller receives the real success or
/// failure once the loop thread has processed the command.
pub enum LifecycleCommand {
    /// Add a new execution client to the running node.
    AddExecClient(
        Box<LiveExecutionClient>,
        tokio::sync::oneshot::Sender<LifecycleCommandResponse>,
    ),
    /// Remove an execution client by its ID.
    RemoveExecClient(
        ClientId,
        tokio::sync::oneshot::Sender<LifecycleCommandResponse>,
    ),
    /// Add a Python strategy to the running node.
    ///
    /// The raw Python instance is registered on the loop thread, where the trader lives.
    #[cfg(feature = "python")]
    AddStrategy(
        Py<PyAny>,
        tokio::sync::oneshot::Sender<LifecycleCommandResponse>,
    ),
    /// Remove a strategy by its ID.
    #[cfg(feature = "python")]
    RemoveStrategy(
        StrategyId,
        tokio::sync::oneshot::Sender<LifecycleCommandResponse>,
    ),
}

impl Debug for LifecycleCommand {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::AddExecClient(client, _) => f.debug_tuple("AddExecClient").field(client).finish(),
            Self::RemoveExecClient(client_id, _) => {
                f.debug_tuple("RemoveExecClient").field(client_id).finish()
            }
            #[cfg(feature = "python")]
            Self::AddStrategy(_, _) => f.debug_tuple("AddStrategy").finish(),
            #[cfg(feature = "python")]
            Self::RemoveStrategy(strategy_id, _) => {
                f.debug_tuple("RemoveStrategy").field(strategy_id).finish()
            }
        }
    }
}
