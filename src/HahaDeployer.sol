// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {HahaNamePolicy} from "./HahaNamePolicy.sol";
import {HahaMetadata} from "./HahaMetadata.sol";
import {HahaResolver} from "./HahaResolver.sol";
import {HahaRegistry} from "./HahaRegistry.sol";
import {HahaRegistrar} from "./HahaRegistrar.sol";
import {HahaAgentIdentity} from "./HahaAgentIdentity.sol";
import {HahaPoints} from "./HahaPoints.sol";
import {HahaReputation} from "./HahaReputation.sol";
import {HahaMarketplace} from "./HahaMarketplace.sol";

contract HahaDeployer {

    error ZeroAddress();
    error NotBootstrappable();
    error AlreadyBootstrapped();
    error DependencyMismatch(string field, address expected, address actual);
    error PolicyCountMismatch();


    HahaNamePolicy public immutable policy;
    HahaMetadata public immutable metadata;
    HahaResolver public immutable resolver;
    HahaRegistry public immutable registry;
    HahaRegistrar public immutable registrar;
    HahaAgentIdentity public immutable identity;
    HahaPoints public immutable points;
    HahaReputation public immutable reputation;
    HahaMarketplace public immutable marketplace;

    address public immutable admin;
    address public immutable feeReceiver;
    address public immutable aiRegistry;


    constructor(address[9] memory addrs, address admin_, address feeReceiver_, address aiRegistry_) {
        policy = HahaNamePolicy(_nz(addrs[0]));
        metadata = HahaMetadata(_nz(addrs[1]));
        resolver = HahaResolver(_nz(addrs[2]));
        registry = HahaRegistry(_nz(addrs[3]));
        registrar = HahaRegistrar(_nz(addrs[4]));
        identity = HahaAgentIdentity(_nz(addrs[5]));
        points = HahaPoints(_nz(addrs[6]));
        reputation = HahaReputation(_nz(addrs[7]));
        marketplace = HahaMarketplace(_nz(addrs[8]));

        admin = _nz(admin_);
        feeReceiver = _nz(feeReceiver_);
        aiRegistry = _nz(aiRegistry_);

        _checkDependencies();

        if (policy.bannedCount() != 208 || policy.reservedCount() != 61) {
            revert PolicyCountMismatch();
        }

        if (registry.bootstrapped()) revert AlreadyBootstrapped();
        registry.bootstrap();
    }


    function addresses() external view returns (address[9] memory out) {
        out = [
            address(policy),
            address(metadata),
            address(resolver),
            address(registry),
            address(registrar),
            address(identity),
            address(points),
            address(reputation),
            address(marketplace)
        ];
    }


    function _checkDependencies() private view {
        _eq("registry.registrar", registry.registrar(), address(registrar));
        _eq("registry.resolver", registry.canonicalResolver(), address(resolver));
        _eq("registry.factory", registry.factory(), address(this));

        _eq("resolver.registry", resolver.registry(), address(registry));
        _eq("resolver.registrar", resolver.registrar(), address(registrar));

        _eq("registrar.registry", registrar.registry(), address(registry));
        _eq("registrar.resolver", registrar.resolver(), address(resolver));
        _eq("registrar.metadata", registrar.metadata(), address(metadata));
        _eq("registrar.points", registrar.points(), address(points));
        _eq("registrar.identity", registrar.identity(), address(identity));
        _eq("registrar.policy", registrar.policy(), address(policy));
        _eq("registrar.aiRegistry", registrar.aiRegistry(), address(aiRegistry));
        _eq("registrar.admin", registrar.admin(), admin);
        _eq("registrar.feeReceiver", registrar.feeReceiver(), feeReceiver);

        _eq("identity.registrar", identity.registrar(), address(registrar));
        _eq("identity.resolver", identity.resolver(), address(resolver));
        _eq("identity.points", identity.points(), address(points));
        _eq("identity.aiRegistry", identity.aiRegistry(), address(aiRegistry));

        _eq("points.registrar", points.registrar(), address(registrar));
        _eq("points.aiRegistry", points.aiRegistry(), address(aiRegistry));
        _eq("points.admin", points.admin(), admin);

        _eq("reputation.identity", reputation.identity(), address(identity));
        _eq("reputation.aiRegistry", reputation.aiRegistry(), address(aiRegistry));
        _eq("reputation.points", reputation.points(), address(points));

        _eq("marketplace.registrar", marketplace.registrar(), address(registrar));
        _eq("marketplace.feeReceiver", marketplace.feeReceiver(), feeReceiver);
    }

    function _eq(string memory field, address expected, address actual) private pure {
        if (expected != actual) revert DependencyMismatch(field, expected, actual);
    }

    function _nz(address a) private pure returns (address) {
        if (a == address(0)) revert ZeroAddress();
        return a;
    }
}
